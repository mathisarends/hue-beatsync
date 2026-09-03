package commands

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"strings"

	"github.com/mathisarends/hue-beatsync/cli/internal/client"
	"github.com/mathisarends/hue-beatsync/cli/internal/lichtorgel"
	"github.com/ogen-go/ogen/validate"
)

type commandError struct {
	Code     string
	Message  string
	Hint     string
	Status   int
	ExitCode int
}

func (e *commandError) Error() string { return e.Message }

// The server documents only its validation errors as schemas; every other
// status arrives bare and is handled by normalizeError.
func apiFailure(operation string, response any) error {
	switch result := response.(type) {
	case *client.HTTPValidationError:
		return validationFailure(result)
	default:
		return fmt.Errorf("unexpected %s response %T", operation, response)
	}
}

func validationFailure(response *client.HTTPValidationError) error {
	issues := make([]string, 0, len(response.Detail))
	for _, issue := range response.Detail {
		issues = append(issues, location(issue.Loc)+": "+issue.Msg)
	}
	message := "the request was rejected"
	if len(issues) > 0 {
		message = issues[0]
	}
	return &commandError{
		Code:     "invalid_request",
		Message:  message,
		Hint:     strings.Join(issues[min(1, len(issues)):], "; "),
		Status:   http.StatusUnprocessableEntity,
		ExitCode: 2,
	}
}

// location renders the "body.audio.gain" path FastAPI reports for a rejected
// field; integer segments are list indices.
func location(parts []client.ValidationErrorLocItem) string {
	var path strings.Builder
	for _, part := range parts {
		switch part.Type {
		case client.StringValidationErrorLocItem:
			if path.Len() > 0 {
				path.WriteByte('.')
			}
			path.WriteString(part.String)
		case client.IntValidationErrorLocItem:
			fmt.Fprintf(&path, "[%d]", part.Int)
		}
	}
	return path.String()
}

// normalizeError gives an undocumented status - the 409 of a stream already
// running, the 503 of an unreachable bridge - the shape of a documented one,
// carrying the server's own `detail` text.
func normalizeError(err error) error {
	var statusErr *validate.UnexpectedStatusCodeError
	if !errors.As(err, &statusErr) {
		return connectionFailure(err)
	}
	message := http.StatusText(statusErr.StatusCode)
	if detail, ok := detailFrom(statusErr); ok {
		message = detail
	}
	return &commandError{
		Code:     statusCode(statusErr.StatusCode),
		Message:  message,
		Hint:     statusHint(statusErr.StatusCode),
		Status:   statusErr.StatusCode,
		ExitCode: 1,
	}
}

func detailFrom(statusErr *validate.UnexpectedStatusCodeError) (string, bool) {
	if statusErr.Payload == nil || statusErr.Payload.Body == nil {
		return "", false
	}
	body, err := io.ReadAll(statusErr.Payload.Body)
	statusErr.Payload.Body = io.NopCloser(bytes.NewReader(body))
	if err != nil {
		return "", false
	}
	var payload struct {
		Detail any `json:"detail"`
	}
	if json.Unmarshal(body, &payload) != nil || payload.Detail == nil {
		return "", false
	}
	if detail, ok := payload.Detail.(string); ok {
		return detail, true
	}
	encoded, err := json.Marshal(payload.Detail)
	if err != nil {
		return "", false
	}
	return string(encoded), true
}

func statusCode(status int) string {
	switch status {
	case http.StatusConflict:
		return "conflict"
	case http.StatusServiceUnavailable:
		return "unavailable"
	default:
		return "api"
	}
}

func statusHint(status int) string {
	switch status {
	case http.StatusConflict:
		return "Run: lichtorgel status"
	case http.StatusServiceUnavailable:
		return "The audio backend or the Hue bridge could not be reached. Run: lichtorgel doctor"
	default:
		return ""
	}
}

// A failed dial is matched rather than the refusal text, which Windows spells
// differently from everyone else.
func connectionFailure(err error) error {
	var opErr *net.OpError
	if !errors.As(err, &opErr) || opErr.Op != "dial" {
		return err
	}
	return &commandError{
		Code:     "unreachable",
		Message:  "no lichtorgel server answered",
		Hint:     "Start it with scripts/serve.sh, or point --api-url at the one you are running.",
		ExitCode: 1,
	}
}

func writeError(writer io.Writer, outputJSON bool, err error) int {
	err = normalizeError(err)
	code, message, hint, status, exitCode := "error", err.Error(), "", 0, 1
	var commandErr *commandError
	var configErr *lichtorgel.ConfigError
	switch {
	case errors.As(err, &commandErr):
		code, message, hint, status = commandErr.Code, commandErr.Message, commandErr.Hint, commandErr.Status
		if commandErr.ExitCode != 0 {
			exitCode = commandErr.ExitCode
		}
	case errors.As(err, &configErr):
		code, message, hint, exitCode = "missing_config", configErr.Message, configErr.Hint, 2
	}
	if outputJSON {
		details := map[string]any{"code": code, "message": message}
		if hint != "" {
			details["hint"] = hint
		}
		if status != 0 {
			details["status"] = status
		}
		encoder := json.NewEncoder(writer)
		encoder.SetIndent("", "  ")
		_ = encoder.Encode(map[string]any{"error": details})
		return exitCode
	}
	_, _ = fmt.Fprintf(writer, "Error: %s\n", message)
	if hint != "" {
		_, _ = fmt.Fprintf(writer, "Hint: %s\n", hint)
	}
	return exitCode
}
