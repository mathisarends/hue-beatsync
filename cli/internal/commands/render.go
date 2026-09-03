package commands

import (
	"bytes"
	"fmt"
	"io"
	"strconv"
	"strings"
	"text/tabwriter"
)

const (
	indent     = "  "
	nextIndent = "        "
)

type emptyState struct {
	Message string
	Hint    string
}

func writeTable(writer io.Writer, columns []string, rows [][]string, empty emptyState) error {
	if len(rows) == 0 {
		return writeLines(writer, empty.Message, empty.Hint)
	}
	if _, err := fmt.Fprintln(writer); err != nil {
		return err
	}
	var padded bytes.Buffer
	table := tabwriter.NewWriter(&padded, 0, 4, 2, ' ', 0)
	if len(columns) > 0 {
		if _, err := fmt.Fprintln(table, indent+strings.Join(columns, "\t")); err != nil {
			return err
		}
	}
	for _, row := range rows {
		if _, err := fmt.Fprintln(table, indent+strings.Join(oneLine(row), "\t")); err != nil {
			return err
		}
	}
	if err := table.Flush(); err != nil {
		return err
	}
	// An empty trailing cell still gets padded, so trim what tabwriter added.
	for line := range strings.Lines(padded.String()) {
		if _, err := fmt.Fprintln(writer, strings.TrimRight(line, " \n")); err != nil {
			return err
		}
	}
	return nil
}

// oneLine keeps a cell on its row. Audio backends report driver names verbatim,
// and some of them carry a line break, which would otherwise tear the table in
// half. Only the rendering is affected: --json still shows the real name.
func oneLine(row []string) []string {
	flattened := make([]string, 0, len(row))
	for _, cell := range row {
		flattened = append(flattened, flatten(cell))
	}
	return flattened
}

func flatten(text string) string {
	return strings.Join(strings.Fields(text), " ")
}

type recordField struct {
	Name  string
	Value string
}

func writeRecord(writer io.Writer, fields ...recordField) error {
	if _, err := fmt.Fprintln(writer); err != nil {
		return err
	}
	table := tabwriter.NewWriter(writer, 0, 4, 2, ' ', 0)
	for _, field := range fields {
		if _, err := fmt.Fprintf(table, "%s%s\t%s\n", indent, field.Name, field.Value); err != nil {
			return err
		}
	}
	return table.Flush()
}

func writeNext(writer io.Writer, steps ...string) error {
	if len(steps) == 0 {
		return nil
	}
	if _, err := fmt.Fprintf(writer, "\n%sNext  %s\n", indent, steps[0]); err != nil {
		return err
	}
	for _, step := range steps[1:] {
		if _, err := fmt.Fprintln(writer, nextIndent+step); err != nil {
			return err
		}
	}
	return nil
}

func writeLines(writer io.Writer, lines ...string) error {
	if _, err := fmt.Fprintln(writer); err != nil {
		return err
	}
	for _, line := range lines {
		if line == "" {
			continue
		}
		if _, err := fmt.Fprintln(writer, indent+line); err != nil {
			return err
		}
	}
	return nil
}

func formatNumber(value float64) string {
	return strconv.FormatFloat(value, 'f', -1, 64)
}

func formatHertz(value float64) string {
	if value >= 1000 {
		return formatNumber(value/1000) + " kHz"
	}
	return formatNumber(value) + " Hz"
}
