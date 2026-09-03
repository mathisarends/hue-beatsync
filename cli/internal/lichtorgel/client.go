package lichtorgel

import (
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/mathisarends/hue-beatsync/cli/internal/client"
)

// Starting a stream connects to the bridge and opens the audio device, both of
// which are slower than a plain read, so the timeout is generous.
const defaultTimeout = 65 * time.Second

type ConfigError struct {
	Message string
	Hint    string
}

func (e *ConfigError) Error() string { return e.Message }

func NewClient(config Config, options ...client.ClientOption) (*client.Client, error) {
	if strings.TrimSpace(config.BaseURL) == "" {
		return nil, &ConfigError{
			Message: "LICHTORGEL_API_URL is empty",
			Hint:    "Set LICHTORGEL_API_URL, or pass --api-url http://127.0.0.1:8765.",
		}
	}
	clientOptions := []client.ClientOption{client.WithClient(&http.Client{Timeout: defaultTimeout})}
	clientOptions = append(clientOptions, options...)
	apiClient, err := client.NewClient(strings.TrimRight(config.BaseURL, "/"), clientOptions...)
	if err != nil {
		return nil, fmt.Errorf("configure API client: %w", err)
	}
	return apiClient, nil
}
