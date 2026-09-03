package commands

import (
	"fmt"
	"slices"
	"strconv"
	"strings"

	"github.com/mathisarends/hue-beatsync/cli/internal/client"
)

var modes = []string{"spectrum", "pulse", "sweep"}

// Shared by `start`, which sends these for one run, and `defaults set`, which
// persists them. Every field is a pointer because an unset flag has to stay out
// of the request entirely, or it would overwrite a saved default with a zero.
type settingsFlags struct {
	Area   *string `help:"Hue entertainment area, by name or id." placeholder:"AREA" group:"Stream settings"`
	Device *string `help:"Audio input, by index or part of its name." placeholder:"DEVICE" group:"Stream settings"`

	Exclusive *bool    `negatable:"" help:"Take the input exclusively; WASAPI devices only." group:"Stream settings"`
	Gain      *float64 `help:"Multiply the captured signal before analysis." group:"Stream settings"`

	Sensitivity  *float64 `help:"How readily quiet passages still reach the lights." group:"Stream settings"`
	Gamma        *float64 `help:"Curve applied to the levels; above 1 darkens the middle." group:"Stream settings"`
	Floor        *float64 `help:"Level below which a band counts as silent." group:"Stream settings"`
	MaxFrequency *float64 `name:"max-frequency" help:"Highest frequency the spectrum covers, in Hz." group:"Stream settings"`

	Mode *string `help:"Visual to paint: spectrum, pulse or sweep." placeholder:"MODE" group:"Stream settings"`
	Rate *int    `help:"Frames sent to the bridge per second." group:"Stream settings"`
}

func (f settingsFlags) request() (*client.SyncSettings, bool, error) {
	if err := f.validate(); err != nil {
		return nil, false, err
	}
	settings := &client.SyncSettings{}
	given := false
	if f.Area != nil {
		settings.Area = client.NewOptNilString(*f.Area)
		given = true
	}

	audio := client.AudioSettings{}
	if f.Device != nil {
		audio.Device = client.NewOptAudioSettingsDevice(deviceValue(*f.Device))
	}
	if f.Exclusive != nil {
		audio.Exclusive = client.NewOptNilBool(*f.Exclusive)
	}
	if f.Gain != nil {
		audio.Gain = client.NewOptNilFloat64(*f.Gain)
	}
	if f.Device != nil || f.Exclusive != nil || f.Gain != nil {
		settings.Audio = client.NewOptAudioSettings(audio)
		given = true
	}

	analysis := client.AnalysisSettings{}
	if f.Sensitivity != nil {
		analysis.Sensitivity = client.NewOptNilFloat64(*f.Sensitivity)
	}
	if f.Gamma != nil {
		analysis.Gamma = client.NewOptNilFloat64(*f.Gamma)
	}
	if f.Floor != nil {
		analysis.Floor = client.NewOptNilFloat64(*f.Floor)
	}
	if f.MaxFrequency != nil {
		analysis.MaxFrequency = client.NewOptNilFloat64(*f.MaxFrequency)
	}
	if f.Sensitivity != nil || f.Gamma != nil || f.Floor != nil || f.MaxFrequency != nil {
		settings.Analysis = client.NewOptAnalysisSettings(analysis)
		given = true
	}

	visual := client.VisualSettings{}
	if f.Mode != nil {
		visual.Mode = client.NewOptNilString(*f.Mode)
	}
	if f.Rate != nil {
		visual.Rate = client.NewOptNilInt(*f.Rate)
	}
	if f.Mode != nil || f.Rate != nil {
		settings.Visual = client.NewOptVisualSettings(visual)
		given = true
	}
	return settings, given, nil
}

func (f settingsFlags) validate() error {
	if f.Mode != nil && !slices.Contains(modes, *f.Mode) {
		return &commandError{
			Code:     "usage",
			Message:  fmt.Sprintf("unknown mode %q", *f.Mode),
			Hint:     "Choose from: " + strings.Join(modes, ", "),
			ExitCode: 2,
		}
	}
	if f.Rate != nil && *f.Rate <= 0 {
		return &commandError{Code: "usage", Message: "rate must be positive", ExitCode: 2}
	}
	if f.Gain != nil && *f.Gain <= 0 {
		return &commandError{Code: "usage", Message: "gain must be positive", ExitCode: 2}
	}
	return nil
}

// The server's own convention: a number is an index, anything else is matched
// against the device names.
func deviceValue(value string) client.AudioSettingsDevice {
	if index, err := strconv.Atoi(strings.TrimSpace(value)); err == nil {
		return client.NewIntAudioSettingsDevice(index)
	}
	return client.NewStringAudioSettingsDevice(value)
}

func describeDevice(device client.OptAudioSettingsDevice) (string, bool) {
	value, ok := device.Get()
	if !ok {
		return "", false
	}
	switch value.Type {
	case client.IntAudioSettingsDevice:
		return strconv.Itoa(value.Int), true
	case client.StringAudioSettingsDevice:
		return value.String, true
	default:
		return "", false
	}
}
