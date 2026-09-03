package commands

import (
	"encoding/json"
	"fmt"
	"io"
	"sort"
	"strings"
)

type outputOptions struct {
	JSON    bool
	Fields  string
	Compact bool
}

func writeOutput(writer io.Writer, options outputOptions, value any, human func() error) error {
	if !options.JSON && strings.TrimSpace(options.Fields) == "" {
		return human()
	}
	projected, err := projectFields(value, options.Fields)
	if err != nil {
		return err
	}
	encoder := json.NewEncoder(writer)
	encoder.SetEscapeHTML(false)
	if !options.Compact {
		encoder.SetIndent("", "  ")
	}
	return encoder.Encode(projected)
}

func projectFields(value any, fieldList string) (any, error) {
	if strings.TrimSpace(fieldList) == "" {
		return value, nil
	}
	data, err := json.Marshal(value)
	if err != nil {
		return nil, fmt.Errorf("prepare field projection: %w", err)
	}
	var decoded any
	if err := json.Unmarshal(data, &decoded); err != nil {
		return nil, fmt.Errorf("prepare field projection: %w", err)
	}

	fields := splitFields(fieldList)
	available := map[string]struct{}{}
	project := func(object map[string]any) map[string]any {
		selected := make(map[string]any, len(fields))
		for key := range object {
			available[key] = struct{}{}
		}
		for _, field := range fields {
			if item, ok := object[field]; ok {
				selected[field] = item
			}
		}
		return selected
	}

	var result any
	switch typed := decoded.(type) {
	case map[string]any:
		result = project(typed)
	case []any:
		items := make([]any, 0, len(typed))
		for _, item := range typed {
			object, ok := item.(map[string]any)
			if !ok {
				return nil, &commandError{Code: "invalid_fields", Message: "--fields requires an object or list of objects", ExitCode: 2}
			}
			items = append(items, project(object))
		}
		result = items
	default:
		return nil, &commandError{Code: "invalid_fields", Message: "--fields requires an object or list of objects", ExitCode: 2}
	}
	if len(available) == 0 {
		return result, nil
	}
	for _, field := range fields {
		if _, ok := available[field]; !ok {
			keys := make([]string, 0, len(available))
			for key := range available {
				keys = append(keys, key)
			}
			sort.Strings(keys)
			return nil, &commandError{
				Code:     "unknown_field",
				Message:  fmt.Sprintf("unknown field %q", field),
				Hint:     "Available fields: " + strings.Join(keys, ", "),
				ExitCode: 2,
			}
		}
	}
	return result, nil
}

func splitFields(value string) []string {
	seen := map[string]bool{}
	var fields []string
	for _, field := range strings.Split(value, ",") {
		field = strings.TrimSpace(field)
		if field != "" && !seen[field] {
			fields = append(fields, field)
			seen[field] = true
		}
	}
	return fields
}
