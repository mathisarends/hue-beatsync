package commands

import (
	"fmt"
	"io"
	"os"
	"strings"

	"golang.org/x/term"
)

const windowSize = 9

// errNoRawMode means the terminal cannot be put into raw mode -- a pipe, or
// mintty under Git Bash, where native programs get a named pipe rather than a
// console handle. Callers fall back to reading a number.
var errNoRawMode = fmt.Errorf("raw mode unavailable")

type selector struct {
	out      io.Writer
	question string
	choices  []choice
	cursor   int
	offset   int
	drawn    int
	color    bool
}

func (s *selector) style(code, text string) string {
	if !s.color {
		return text
	}
	return code + text + "\x1b[0m"
}

func selectWithArrowKeys(in io.Reader, out io.Writer, question string, choices []choice) (choice, error) {
	file, ok := in.(*os.File)
	if !ok {
		return choice{}, errNoRawMode
	}
	state, err := term.MakeRaw(int(file.Fd()))
	if err != nil {
		return choice{}, errNoRawMode
	}
	defer func() { _ = term.Restore(int(file.Fd()), state) }()
	restoreVirtualTerminal := enableVirtualTerminal(out)
	defer restoreVirtualTerminal()

	list := &selector{out: out, question: question, choices: choices, color: supportsColor(out)}
	if err := list.draw(); err != nil {
		return choice{}, err
	}
	keys := make([]byte, 3)
	for {
		read, err := file.Read(keys)
		if err != nil {
			return choice{}, errNoRawMode
		}
		switch action := keyAction(keys[:read]); action {
		case actionUp:
			list.move(-1)
		case actionDown:
			list.move(1)
		case actionAccept:
			return list.choices[list.cursor], list.collapse(list.choices[list.cursor].Label)
		case actionCancel:
			if err := list.collapse(""); err != nil {
				return choice{}, err
			}
			return choice{}, errCancelled
		}
		if err := list.draw(); err != nil {
			return choice{}, err
		}
	}
}

type keyPress int

const (
	actionNone keyPress = iota
	actionUp
	actionDown
	actionAccept
	actionCancel
)

func keyAction(keys []byte) keyPress {
	if len(keys) >= 3 && keys[0] == 0x1b && keys[1] == '[' {
		switch keys[2] {
		case 'A':
			return actionUp
		case 'B':
			return actionDown
		}
		return actionNone
	}
	switch keys[0] {
	case '\r', '\n':
		return actionAccept
	case 0x03, 0x1b, 'q': // Ctrl-C, Escape, q
		return actionCancel
	case 'k':
		return actionUp
	case 'j':
		return actionDown
	}
	return actionNone
}

func (s *selector) move(by int) {
	s.cursor = min(max(s.cursor+by, 0), len(s.choices)-1)
	s.offset = min(max(s.offset, s.cursor-windowSize+1), s.cursor)
}

func (s *selector) draw() error {
	var page strings.Builder
	if s.drawn > 0 {
		fmt.Fprintf(&page, "\x1b[%dA", s.drawn)
	}
	lines := 0
	write := func(format string, args ...any) {
		fmt.Fprintf(&page, "\x1b[2K"+format+"\r\n", args...)
		lines++
	}
	write("")
	write("%s%s", indent, s.question)
	write("")
	visible := min(len(s.choices), windowSize)
	for row := range visible {
		index := s.offset + row
		if index == s.cursor {
			write("%s%s", indent, s.style("\x1b[7m", " "+s.choices[index].Label+" "))
			continue
		}
		write("%s %s", indent, s.choices[index].Label)
	}
	write("")
	write("%s%s", indent, s.style("\x1b[2m", "↑ ↓ to move, Enter to pick, q to cancel"+s.scrollHint(visible)))
	s.drawn = lines
	_, err := io.WriteString(s.out, page.String())
	return err
}

func (s *selector) scrollHint(visible int) string {
	if visible == len(s.choices) {
		return ""
	}
	return fmt.Sprintf("  --  %d of %d", s.cursor+1, len(s.choices))
}

// collapse erases the list and leaves a single line naming the answer, so a
// finished wizard reads as a short transcript rather than a wall of options.
func (s *selector) collapse(answer string) error {
	var page strings.Builder
	fmt.Fprintf(&page, "\x1b[%dA", s.drawn)
	for range s.drawn {
		page.WriteString("\x1b[2K\r\n")
	}
	fmt.Fprintf(&page, "\x1b[%dA", s.drawn)
	if answer != "" {
		fmt.Fprintf(&page, "\r\n%s%s  %s\r\n", indent, s.question, s.style("\x1b[1m", answer))
	}
	s.drawn = 0
	_, err := io.WriteString(s.out, page.String())
	return err
}
