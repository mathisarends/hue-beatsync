//go:build !windows

package commands

import "io"

func enableVirtualTerminal(io.Writer) func() { return func() {} }
