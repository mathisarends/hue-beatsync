package commands

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"strings"
	"testing"
)

func TestNoArgumentsPrintsHelp(t *testing.T) {
	t.Parallel()
	var stdout, stderr bytes.Buffer
	if exitCode := Run(context.Background(), nil, strings.NewReader(""), &stdout, &stderr); exitCode != 0 {
		t.Fatalf("exit = %d, stderr = %s", exitCode, stderr.String())
	}
	if !strings.Contains(stdout.String(), "Usage: lichtorgel") {
		t.Fatalf("stdout = %s", stdout.String())
	}
}

func TestVersionSupportsJSON(t *testing.T) {
	var stdout, stderr bytes.Buffer
	exitCode := Run(context.Background(), []string{"version", "--json", "--compact"}, strings.NewReader(""), &stdout, &stderr)
	if exitCode != 0 {
		t.Fatalf("exit = %d, stderr = %s", exitCode, stderr.String())
	}
	var result map[string]any
	if err := json.Unmarshal(stdout.Bytes(), &result); err != nil {
		t.Fatal(err)
	}
	if result["version"] != Version {
		t.Fatalf("result = %#v", result)
	}
}

func TestUsageErrorIsJSONWhenRequested(t *testing.T) {
	t.Parallel()
	var stdout, stderr bytes.Buffer
	exitCode := Run(context.Background(), []string{"not-a-command", "--json"}, strings.NewReader(""), &stdout, &stderr)
	if exitCode != 2 || stdout.Len() != 0 || !strings.Contains(stderr.String(), `"code": "usage"`) {
		t.Fatalf("exit = %d, stdout = %q, stderr = %q", exitCode, stdout.String(), stderr.String())
	}
}

func TestUnknownModeIsRejectedBeforeTheRequest(t *testing.T) {
	stdout, stderr, exitCode := runTestCLI(t, "http://127.0.0.1:1", "start", "--mode", "strobe", "--json")
	if exitCode != 2 || stdout != "" {
		t.Fatalf("exit = %d, stdout = %q", exitCode, stdout)
	}
	if !strings.Contains(stderr, "unknown mode") || !strings.Contains(stderr, "spectrum, pulse, sweep") {
		t.Fatalf("stderr = %s", stderr)
	}
}

func TestConflictCarriesTheServerDetail(t *testing.T) {
	server := errorServer(t, http.StatusConflict, "already streaming to 'Bedroom'")
	stdout, stderr, exitCode := runTestCLI(t, server.URL, "start", "--json")
	if exitCode != 1 || stdout != "" {
		t.Fatalf("exit = %d, stdout = %q", exitCode, stdout)
	}
	if !strings.Contains(stderr, `"code": "conflict"`) || !strings.Contains(stderr, "already streaming") {
		t.Fatalf("stderr = %s", stderr)
	}
}

func TestUnavailableBackendIsReportedWithAHint(t *testing.T) {
	server := errorServer(t, http.StatusServiceUnavailable, "No audio input device found.")
	_, stderr, exitCode := runTestCLI(t, server.URL, "device", "list", "--json")
	if exitCode != 1 || !strings.Contains(stderr, `"status": 503`) || !strings.Contains(stderr, "lichtorgel doctor") {
		t.Fatalf("exit = %d, stderr = %s", exitCode, stderr)
	}
}

func TestUnreachableServerNamesTheProblem(t *testing.T) {
	// Port 1 is reserved and never listening, so the dial is refused at once.
	_, stderr, exitCode := runTestCLI(t, "http://127.0.0.1:1", "status")
	if exitCode != 1 || !strings.Contains(stderr, "no lichtorgel server answered") {
		t.Fatalf("exit = %d, stderr = %s", exitCode, stderr)
	}
}

func TestWriteOutputProjectsFields(t *testing.T) {
	t.Parallel()
	var output bytes.Buffer
	err := writeOutput(&output, outputOptions{Fields: "index,name", Compact: true}, []map[string]any{
		{"index": 1, "name": "Speakers", "host_api": "WASAPI"},
	}, func() error { return nil })
	if err != nil {
		t.Fatal(err)
	}
	var rows []map[string]any
	if err := json.Unmarshal(output.Bytes(), &rows); err != nil {
		t.Fatal(err)
	}
	if len(rows) != 1 || len(rows[0]) != 2 || rows[0]["name"] != "Speakers" {
		t.Fatalf("rows = %#v", rows)
	}
}

func TestUnknownFieldIsActionable(t *testing.T) {
	t.Parallel()
	_, err := projectFields(map[string]any{"index": 1, "name": "Speakers"}, "naem")
	if err == nil || !strings.Contains(err.Error(), "unknown field") {
		t.Fatalf("error = %v", err)
	}
	var commandErr *commandError
	if !errors.As(err, &commandErr) || commandErr.Hint != "Available fields: index, name" {
		t.Fatalf("error = %#v", err)
	}
}
