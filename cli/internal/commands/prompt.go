package commands

import (
	"bufio"
	"errors"
	"fmt"
	"io"
	"strconv"
	"strings"
)

type choice struct {
	Label string
	Value any
}

type prompter struct {
	raw  io.Reader
	in   *bufio.Reader
	out  io.Writer
	hint string
}

func newPrompter(runtime *Runtime, hint string) *prompter {
	return &prompter{
		raw:  runtime.stdin,
		in:   bufio.NewReader(runtime.stdin),
		out:  runtime.stdout,
		hint: hint,
	}
}

// Arrow keys where raw mode is available, a numbered list otherwise.
func (p *prompter) selectChoice(question string, choices []choice) (choice, error) {
	if len(choices) == 0 {
		return choice{}, p.fail(fmt.Sprintf("nothing to choose from for %q", question))
	}
	if len(choices) == 1 {
		return choices[0], p.write(fmt.Sprintf("\n%s%s  %s\n", indent, question, choices[0].Label))
	}
	if err := p.write("\n"); err != nil {
		return choice{}, err
	}
	picked, err := selectWithArrowKeys(p.raw, p.out, question, choices)
	if err == nil {
		return picked, nil
	}
	if !errors.Is(err, errNoRawMode) {
		return choice{}, err
	}
	if err := p.write(fmt.Sprintf("%s%s\n\n", indent, question)); err != nil {
		return choice{}, err
	}
	for index, option := range choices {
		if err := p.write(fmt.Sprintf("%s%3d  %s\n", indent, index+1, option.Label)); err != nil {
			return choice{}, err
		}
	}
	for {
		answer, err := p.ask(fmt.Sprintf("Number [1-%d]", len(choices)), "1")
		if err != nil {
			return choice{}, err
		}
		number, err := strconv.Atoi(answer)
		if err != nil || number < 1 || number > len(choices) {
			if err := p.write(fmt.Sprintf("%sPick a number between 1 and %d.\n", indent, len(choices))); err != nil {
				return choice{}, err
			}
			continue
		}
		return choices[number-1], nil
	}
}

func (p *prompter) confirm(question string, byDefault bool) (bool, error) {
	suffix, fallback := " [y/N]", "n"
	if byDefault {
		suffix, fallback = " [Y/n]", "y"
	}
	answer, err := p.ask(question+suffix, fallback)
	if err != nil {
		return false, err
	}
	switch strings.ToLower(answer) {
	case "y", "yes":
		return true, nil
	default:
		return false, nil
	}
}

func (p *prompter) ask(question, fallback string) (string, error) {
	if err := p.write(fmt.Sprintf("\n%s%s: ", indent, question)); err != nil {
		return "", err
	}
	line, err := p.in.ReadString('\n')
	if err != nil && (!errors.Is(err, io.EOF) || strings.TrimSpace(line) == "") {
		return "", p.fail("stdin closed before the question was answered")
	}
	if answer := strings.TrimSpace(line); answer != "" {
		return answer, nil
	}
	return fallback, nil
}

func (p *prompter) write(text string) error {
	_, err := fmt.Fprint(p.out, text)
	return err
}

func (p *prompter) fail(message string) error {
	return &commandError{Code: "no_input", Message: message, Hint: p.hint, ExitCode: 2}
}
