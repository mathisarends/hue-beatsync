//go:build windows

package commands

import (
	"io"
	"os"

	"golang.org/x/sys/windows"
)

// enableVirtualTerminal turns on ANSI handling for the console. Windows
// Terminal has it on already; the older conhost prints the escapes verbatim
// without this. The returned function restores the previous mode.
func enableVirtualTerminal(out io.Writer) func() {
	file, ok := out.(*os.File)
	if !ok {
		return func() {}
	}
	handle := windows.Handle(file.Fd())
	var mode uint32
	if err := windows.GetConsoleMode(handle, &mode); err != nil {
		return func() {}
	}
	if mode&windows.ENABLE_VIRTUAL_TERMINAL_PROCESSING != 0 {
		return func() {}
	}
	if err := windows.SetConsoleMode(handle, mode|windows.ENABLE_VIRTUAL_TERMINAL_PROCESSING); err != nil {
		return func() {}
	}
	return func() { _ = windows.SetConsoleMode(handle, mode) }
}
