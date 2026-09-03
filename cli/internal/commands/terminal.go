package commands

import (
	"io"
	"os"

	"github.com/mattn/go-isatty"
)

// isTerminal reports whether a stream is attached to something a person is
// looking at. IsCygwinTerminal matters on Windows: mintty, which Git Bash
// uses, hands native programs a named pipe rather than a console handle, so
// the plain check would call a real terminal a redirect.
func isTerminal(stream any) bool {
	file, ok := stream.(*os.File)
	if !ok {
		return false
	}
	return isatty.IsTerminal(file.Fd()) || isatty.IsCygwinTerminal(file.Fd())
}

func supportsColor(writer io.Writer) bool {
	if _, disabled := os.LookupEnv("NO_COLOR"); disabled {
		return false
	}
	return isTerminal(writer)
}
