package commands

import (
	"context"
	"errors"
	"fmt"
	"io"
	"strings"

	"github.com/alecthomas/kong"
	"github.com/mathisarends/hue-beatsync/cli/internal/client"
	"github.com/mathisarends/hue-beatsync/cli/internal/lichtorgel"
)

var Version = "dev"

const description = `Drive the Hue lights from what the machine is playing.

Every example below is a full command, including the "lichtorgel" itself.

First run: "lichtorgel setup" picks the entertainment area and the audio input
and saves both, "lichtorgel doctor" confirms the server can reach them, and
"lichtorgel start" opens the stream. "lichtorgel stop" closes it again.

Nothing has to be saved: every setting is also a flag on "lichtorgel start",
and a flag always wins over the saved default.

Every command prints a readable summary, or stable JSON with --json.`

type commandTree struct {
	JSON    bool   `help:"Emit stable JSON on stdout."`
	Fields  string `help:"Comma-separated top-level fields to include; implies --json." placeholder:"FIELD,..."`
	Compact bool   `help:"Emit compact rather than indented JSON."`
	EnvFile string `help:"Path to a dotenv configuration file." default:".env" type:"path"`
	APIURL  string `name:"api-url" help:"Override LICHTORGEL_API_URL." placeholder:"URL"`

	Start  startCommand  `cmd:"" help:"Start the stream."`
	Stop   stopCommand   `cmd:"" help:"Stop the running stream."`
	Status statusCommand `cmd:"" help:"Report whether a stream is running."`

	Area   areaCommand   `cmd:"" help:"List the Hue entertainment areas, or save the one to light up."`
	Device deviceCommand `cmd:"" help:"List the audio inputs, or save the one to listen to."`
	Setup  setupCommand  `cmd:"" help:"Pick an area and an audio input, and save both."`

	Defaults defaultsCommand `cmd:"" help:"Read or save the settings a bare start falls back to."`
	Doctor   doctorCommand   `cmd:"" help:"Check that the server can reach the bridge and the sound card."`
	Version  versionCommand  `cmd:"" help:"Print version information."`
}

type versionCommand struct{}

type Runtime struct {
	ctx    context.Context
	root   *commandTree
	config lichtorgel.Config
	stdin  io.Reader
	stdout io.Writer
	stderr io.Writer
}

// Run executes the CLI and returns a process exit code.
func Run(ctx context.Context, args []string, stdin io.Reader, stdout, stderr io.Writer) int {
	if len(args) == 0 {
		args = []string{"--help"}
	}
	if len(args) == 1 && args[0] == "--version" {
		_, _ = fmt.Fprintln(stdout, Version)
		return 0
	}

	var root commandTree
	parser, err := kong.New(
		&root,
		kong.Name("lichtorgel"),
		kong.Description(description),
		kong.UsageOnError(),
		kong.Writers(stdout, stderr),
		kong.Exit(func(code int) { panic(parserExit(code)) }),
	)
	if err != nil {
		return writeError(stderr, false, fmt.Errorf("build command tree: %w", err))
	}
	parsed, exited, err := parseArgs(parser, args)
	if exited >= 0 {
		return exited
	}
	if err != nil {
		return writeError(stderr, wantsJSON(args), &commandError{Code: "usage", Message: err.Error(), ExitCode: 2})
	}

	config, err := lichtorgel.LoadConfig(root.EnvFile)
	if err != nil {
		return writeError(stderr, root.JSON || root.Fields != "", err)
	}
	if root.APIURL != "" {
		config.BaseURL = strings.TrimRight(root.APIURL, "/")
	}
	runtime := &Runtime{ctx: ctx, root: &root, config: config, stdin: stdin, stdout: stdout, stderr: stderr}
	if err := parsed.Run(runtime); err != nil {
		var silent *exitCodeError
		if errors.As(err, &silent) {
			return silent.code
		}
		return writeError(stderr, root.JSON || root.Fields != "", err)
	}
	return 0
}

// exitCodeError ends the process with a status and nothing else: the command
// has already printed its answer, and a failure line would contradict it.
type exitCodeError struct{ code int }

func (e *exitCodeError) Error() string { return fmt.Sprintf("exit status %d", e.code) }

type parserExit int

func parseArgs(parser *kong.Kong, args []string) (parsed *kong.Context, exitCode int, err error) {
	exitCode = -1
	defer func() {
		if recovered := recover(); recovered != nil {
			if requested, ok := recovered.(parserExit); ok {
				exitCode = int(requested)
				return
			}
			panic(recovered)
		}
	}()
	parsed, err = parser.Parse(args)
	return parsed, exitCode, err
}

func (r *Runtime) client() (*client.Client, error) {
	return lichtorgel.NewClient(r.config)
}

func (r *Runtime) output(value any, human func() error) error {
	return writeOutput(r.stdout, outputOptions{JSON: r.root.JSON, Fields: r.root.Fields, Compact: r.root.Compact}, value, human)
}

func (r *Runtime) scripted() bool {
	return r.root.JSON || r.root.Fields != ""
}

func (versionCommand) Run(runtime *Runtime) error {
	return runtime.output(map[string]any{"version": Version}, func() error {
		_, err := fmt.Fprintln(runtime.stdout, Version)
		return err
	})
}

func wantsJSON(args []string) bool {
	for _, arg := range args {
		if arg == "--json" || arg == "--fields" || strings.HasPrefix(arg, "--fields=") {
			return true
		}
	}
	return false
}
