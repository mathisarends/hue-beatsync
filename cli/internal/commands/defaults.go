package commands

import (
	"github.com/mathisarends/hue-beatsync/cli/internal/client"
)

type defaultsCommand struct {
	Show defaultsShowCommand `cmd:"" default:"withargs" help:"Show the saved settings."`
	Set  defaultsSetCommand  `cmd:"" help:"Save one or more settings."`
}

type defaultsShowCommand struct{}

type defaultsSetCommand struct {
	Settings settingsFlags `embed:""`
}

func (defaultsShowCommand) Run(runtime *Runtime) error {
	result, err := fetch[*client.SyncSettings](runtime, "read defaults", (*client.Client).GetDefaults)
	if err != nil {
		return err
	}
	return runtime.output(result, func() error {
		return writeDefaults(runtime, result)
	})
}

func (command defaultsSetCommand) Run(runtime *Runtime) error {
	request, given, err := command.Settings.request()
	if err != nil {
		return err
	}
	if !given {
		return &commandError{
			Code:     "usage",
			Message:  "nothing to save",
			Hint:     "Pass at least one setting, e.g. lichtorgel defaults set --mode sweep",
			ExitCode: 2,
		}
	}
	result, err := saveDefaults(runtime, request)
	if err != nil {
		return err
	}
	return runtime.output(result, func() error {
		if err := writeLines(runtime.stdout, "Saved."); err != nil {
			return err
		}
		if err := writeDefaults(runtime, result); err != nil {
			return err
		}
		return writeNext(runtime.stdout, "lichtorgel start")
	})
}

// Only what is actually saved. Printing the built-in fallbacks too would
// suggest they had been chosen.
func writeDefaults(runtime *Runtime, settings *client.SyncSettings) error {
	var fields []recordField
	add := func(name, value string) {
		fields = append(fields, recordField{Name: name, Value: value})
	}
	if area, ok := settings.Area.Get(); ok {
		add("Area", area)
	}
	if audio, ok := settings.Audio.Get(); ok {
		if device, ok := describeDevice(audio.Device); ok {
			add("Device", device)
		}
		if exclusive, ok := audio.Exclusive.Get(); ok {
			add("Exclusive", yesNo(exclusive))
		}
		if gain, ok := audio.Gain.Get(); ok {
			add("Gain", formatNumber(gain))
		}
	}
	if analysis, ok := settings.Analysis.Get(); ok {
		if sensitivity, ok := analysis.Sensitivity.Get(); ok {
			add("Sensitivity", formatNumber(sensitivity))
		}
		if gamma, ok := analysis.Gamma.Get(); ok {
			add("Gamma", formatNumber(gamma))
		}
		if floor, ok := analysis.Floor.Get(); ok {
			add("Floor", formatNumber(floor))
		}
		if maxFrequency, ok := analysis.MaxFrequency.Get(); ok {
			add("Max frequency", formatHertz(maxFrequency))
		}
	}
	if visual, ok := settings.Visual.Get(); ok {
		if mode, ok := visual.Mode.Get(); ok {
			add("Mode", mode)
		}
		if rate, ok := visual.Rate.Get(); ok {
			add("Rate", formatNumber(float64(rate))+" fps")
		}
	}
	if len(fields) == 0 {
		return writeLines(runtime.stdout,
			"Nothing saved yet; every setting falls back to its built-in value.",
			"Run: lichtorgel setup",
		)
	}
	return writeRecord(runtime.stdout, fields...)
}
