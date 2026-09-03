package commands

import (
	"errors"
	"fmt"

	"github.com/mathisarends/hue-beatsync/cli/internal/client"
)

// errCancelled is a decision, not a failure: the user said no.
var errCancelled = errors.New("cancelled")

const setupHint = "Set the two explicitly: lichtorgel area select <name> and lichtorgel device select <name>"

type setupCommand struct{}

func (setupCommand) Run(runtime *Runtime) error {
	if runtime.scripted() {
		return &commandError{
			Code:     "usage",
			Message:  "setup is interactive and cannot be combined with --json or --fields",
			Hint:     setupHint,
			ExitCode: 2,
		}
	}
	areas, err := listAreas(runtime)
	if err != nil {
		return err
	}
	devices, err := listDevices(runtime)
	if err != nil {
		return err
	}
	area, err := pickArea(runtime, areas, "")
	if err != nil {
		return err
	}
	device, err := pickDevice(runtime, devices, "")
	if err != nil {
		return err
	}
	prompt := newPrompter(runtime, setupHint)
	mode, err := prompt.selectChoice("Which visual?", modeChoices())
	if err != nil {
		return err
	}

	summary := fmt.Sprintf("Light up %q from %q, painting %s.", area.Name, device.Name, mode.Value.(string))
	if err := writeLines(runtime.stdout, summary); err != nil {
		return err
	}
	confirmed, err := prompt.confirm("Save this", true)
	if errors.Is(err, errCancelled) || (err == nil && !confirmed) {
		return writeLines(runtime.stdout, "Nothing saved.")
	}
	if err != nil {
		return err
	}

	request := &client.SyncSettings{
		Area: client.NewOptNilString(areaSetting(area, areas)),
		Audio: client.NewOptAudioSettings(client.AudioSettings{
			Device: client.NewOptAudioSettingsDevice(deviceSetting(device, devices, false)),
		}),
		Visual: client.NewOptVisualSettings(client.VisualSettings{
			Mode: client.NewOptNilString(mode.Value.(string)),
		}),
	}
	saved, err := saveDefaults(runtime, request)
	if err != nil {
		return err
	}
	return runtime.output(saved, func() error {
		if err := writeLines(runtime.stdout, "Saved."); err != nil {
			return err
		}
		if err := writeDefaults(runtime, saved); err != nil {
			return err
		}
		return writeNext(runtime.stdout, "lichtorgel start", "lichtorgel doctor")
	})
}

func modeChoices() []choice {
	labels := map[string]string{
		"spectrum": "spectrum  --  each light follows its own frequency band",
		"pulse":    "pulse  --  the whole room breathes with the beat",
		"sweep":    "sweep  --  the beat travels across the room",
	}
	choices := make([]choice, 0, len(modes))
	for _, mode := range modes {
		choices = append(choices, choice{Label: labels[mode], Value: mode})
	}
	return choices
}
