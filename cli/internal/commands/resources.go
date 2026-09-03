package commands

import (
	"fmt"
	"strconv"
	"strings"

	"github.com/mathisarends/hue-beatsync/cli/internal/client"
)

const pickHint = "Pass the value explicitly, e.g. lichtorgel area select \"Living Room\""

type areaCommand struct {
	List   areaListCommand   `cmd:"" default:"withargs" help:"List the entertainment areas the bridge offers."`
	Select areaSelectCommand `cmd:"" help:"Save the area a bare start lights up."`
}

type deviceCommand struct {
	List   deviceListCommand   `cmd:"" default:"withargs" help:"List the audio inputs the server can capture."`
	Select deviceSelectCommand `cmd:"" help:"Save the audio input a bare start listens to."`
}

type areaListCommand struct{}

type deviceListCommand struct{}

type areaSelectCommand struct {
	Area string `arg:"" optional:"" help:"Area name or id; asked for when omitted."`
}

type deviceSelectCommand struct {
	Device  string `arg:"" optional:"" help:"Device index or part of its name; asked for when omitted."`
	ByIndex bool   `help:"Save the index rather than the name. Indices move when the sound hardware changes, so the name is the safer default."`
}

func (areaListCommand) Run(runtime *Runtime) error {
	areas, err := listAreas(runtime)
	if err != nil {
		return err
	}
	return runtime.output(areas, func() error {
		rows := make([][]string, 0, len(areas))
		for _, area := range areas {
			rows = append(rows, []string{
				area.ID, area.Name, strconv.Itoa(area.Channels), streaming(area.Active),
			})
		}
		if err := writeTable(runtime.stdout, []string{"ID", "NAME", "CHANNELS", "STREAMING"}, rows, emptyState{
			Message: "The bridge reports no entertainment areas.",
			Hint:    "Create one in the Hue app under Entertainment, then run this again.",
		}); err != nil {
			return err
		}
		if len(rows) == 0 {
			return nil
		}
		return writeNext(runtime.stdout, "lichtorgel area select <name>")
	})
}

func (deviceListCommand) Run(runtime *Runtime) error {
	devices, err := listDevices(runtime)
	if err != nil {
		return err
	}
	return runtime.output(devices, func() error {
		rows := make([][]string, 0, len(devices))
		for _, device := range devices {
			rows = append(rows, []string{
				indexLabel(device), device.Name, device.HostAPI,
				formatNumber(float64(device.Samplerate)), yesNo(device.SupportsExclusive),
			})
		}
		if err := writeTable(runtime.stdout, []string{"INDEX", "NAME", "HOST API", "RATE", "EXCLUSIVE"}, rows, emptyState{
			Message: "The server reports no audio inputs.",
			Hint:    "Run: lichtorgel doctor",
		}); err != nil {
			return err
		}
		if len(rows) == 0 {
			return nil
		}
		if err := writeLines(runtime.stdout, "* is the input used when none is saved."); err != nil {
			return err
		}
		return writeNext(runtime.stdout, "lichtorgel device select <name>")
	})
}

func (command areaSelectCommand) Run(runtime *Runtime) error {
	areas, err := listAreas(runtime)
	if err != nil {
		return err
	}
	area, err := pickArea(runtime, areas, command.Area)
	if err != nil {
		return err
	}
	saved, err := saveDefaults(runtime, &client.SyncSettings{Area: client.NewOptNilString(areaSetting(area, areas))})
	if err != nil {
		return err
	}
	return runtime.output(saved, func() error {
		if err := writeLines(runtime.stdout, fmt.Sprintf("Saved %q as the area to light up.", area.Name)); err != nil {
			return err
		}
		return writeNext(runtime.stdout, "lichtorgel device select", "lichtorgel start")
	})
}

func (command deviceSelectCommand) Run(runtime *Runtime) error {
	devices, err := listDevices(runtime)
	if err != nil {
		return err
	}
	device, err := pickDevice(runtime, devices, command.Device)
	if err != nil {
		return err
	}
	audio := client.AudioSettings{
		Device: client.NewOptAudioSettingsDevice(deviceSetting(device, devices, command.ByIndex)),
	}
	saved, err := saveDefaults(runtime, &client.SyncSettings{Audio: client.NewOptAudioSettings(audio)})
	if err != nil {
		return err
	}
	return runtime.output(saved, func() error {
		if err := writeLines(runtime.stdout, fmt.Sprintf("Saved %q as the audio input.", device.Name)); err != nil {
			return err
		}
		return writeNext(runtime.stdout, "lichtorgel start")
	})
}

func listAreas(runtime *Runtime) ([]client.AreaInfo, error) {
	return fetch[[]client.AreaInfo](runtime, "list areas", (*client.Client).ListAreas)
}

func listDevices(runtime *Runtime) ([]client.AudioDeviceInfo, error) {
	return fetch[[]client.AudioDeviceInfo](runtime, "list devices", (*client.Client).ListDevices)
}

func saveDefaults(runtime *Runtime, request *client.SyncSettings) (*client.SyncSettings, error) {
	return send[*client.SyncSettings](runtime, "save defaults", (*client.Client).SetDefaults, request)
}

func pickArea(runtime *Runtime, areas []client.AreaInfo, wanted string) (client.AreaInfo, error) {
	if len(areas) == 0 {
		return client.AreaInfo{}, &commandError{
			Code:     "empty",
			Message:  "the bridge reports no entertainment areas",
			Hint:     "Create one in the Hue app under Entertainment, then run this again.",
			ExitCode: 1,
		}
	}
	if strings.TrimSpace(wanted) != "" {
		return matchArea(areas, wanted)
	}
	if runtime.scripted() {
		return client.AreaInfo{}, &commandError{
			Code:     "usage",
			Message:  "an area is required with --json or --fields",
			Hint:     pickHint,
			ExitCode: 2,
		}
	}
	prompt := newPrompter(runtime, pickHint)
	picked, err := prompt.selectChoice("Which entertainment area?", areaChoices(areas))
	if err != nil {
		return client.AreaInfo{}, err
	}
	return areas[picked.Value.(int)], nil
}

func pickDevice(runtime *Runtime, devices []client.AudioDeviceInfo, wanted string) (client.AudioDeviceInfo, error) {
	if len(devices) == 0 {
		return client.AudioDeviceInfo{}, &commandError{
			Code:     "empty",
			Message:  "the server reports no audio inputs",
			Hint:     "Run: lichtorgel doctor",
			ExitCode: 1,
		}
	}
	if strings.TrimSpace(wanted) != "" {
		return matchDevice(devices, wanted)
	}
	if runtime.scripted() {
		return client.AudioDeviceInfo{}, &commandError{
			Code:     "usage",
			Message:  "a device is required with --json or --fields",
			Hint:     "Pass the value explicitly, e.g. lichtorgel device select 3",
			ExitCode: 2,
		}
	}
	prompt := newPrompter(runtime, "Pass the value explicitly, e.g. lichtorgel device select 3")
	picked, err := prompt.selectChoice("Which audio input?", deviceChoices(devices))
	if err != nil {
		return client.AudioDeviceInfo{}, err
	}
	return devices[picked.Value.(int)], nil
}

// Resolved here rather than by the server, so the confirmation can name the
// area that was actually saved.
func matchArea(areas []client.AreaInfo, wanted string) (client.AreaInfo, error) {
	for _, area := range areas {
		if area.ID == wanted || strings.EqualFold(area.Name, wanted) {
			return area, nil
		}
	}
	var matches []client.AreaInfo
	for _, area := range areas {
		if strings.Contains(strings.ToLower(area.Name), strings.ToLower(wanted)) {
			matches = append(matches, area)
		}
	}
	if len(matches) == 1 {
		return matches[0], nil
	}
	names := make([]string, 0, len(areas))
	for _, area := range areas {
		names = append(names, area.Name)
	}
	if len(matches) > 1 {
		ambiguous := make([]string, 0, len(matches))
		for _, area := range matches {
			ambiguous = append(ambiguous, area.Name)
		}
		return client.AreaInfo{}, &commandError{
			Code:     "ambiguous",
			Message:  fmt.Sprintf("%q matches more than one area", wanted),
			Hint:     "Matches: " + strings.Join(ambiguous, ", "),
			ExitCode: 2,
		}
	}
	return client.AreaInfo{}, &commandError{
		Code:     "not_found",
		Message:  fmt.Sprintf("no entertainment area matches %q", wanted),
		Hint:     "Areas: " + strings.Join(names, ", "),
		ExitCode: 2,
	}
}

func matchDevice(devices []client.AudioDeviceInfo, wanted string) (client.AudioDeviceInfo, error) {
	if index, err := strconv.Atoi(strings.TrimSpace(wanted)); err == nil {
		for _, device := range devices {
			if device.Index == index {
				return device, nil
			}
		}
		return client.AudioDeviceInfo{}, &commandError{
			Code:     "not_found",
			Message:  fmt.Sprintf("no audio input has index %d", index),
			Hint:     "Run: lichtorgel device list",
			ExitCode: 2,
		}
	}
	for _, device := range devices {
		if strings.EqualFold(device.Name, wanted) {
			return device, nil
		}
	}
	var matches []client.AudioDeviceInfo
	for _, device := range devices {
		if strings.Contains(strings.ToLower(device.Name), strings.ToLower(wanted)) {
			matches = append(matches, device)
		}
	}
	if len(matches) == 1 {
		return matches[0], nil
	}
	if len(matches) > 1 {
		ambiguous := make([]string, 0, len(matches))
		for _, device := range matches {
			ambiguous = append(ambiguous, fmt.Sprintf("%d %s", device.Index, device.Name))
		}
		return client.AudioDeviceInfo{}, &commandError{
			Code:     "ambiguous",
			Message:  fmt.Sprintf("%q matches more than one audio input", wanted),
			Hint:     "Matches: " + strings.Join(ambiguous, "; ") + ". Pass an index to be exact.",
			ExitCode: 2,
		}
	}
	return client.AudioDeviceInfo{}, &commandError{
		Code:     "not_found",
		Message:  fmt.Sprintf("no audio input matches %q", wanted),
		Hint:     "Run: lichtorgel device list",
		ExitCode: 2,
	}
}

// The name is what a person recognises in lichtorgel.yml; the id is the
// fallback when the name would be ambiguous.
func areaSetting(area client.AreaInfo, areas []client.AreaInfo) string {
	named := 0
	for _, other := range areas {
		if strings.EqualFold(other.Name, area.Name) {
			named++
		}
	}
	if named > 1 {
		return area.ID
	}
	return area.Name
}

// The name outlives the index, which the audio backend hands out in
// enumeration order and reshuffles as soon as a headset is plugged in.
func deviceSetting(device client.AudioDeviceInfo, devices []client.AudioDeviceInfo, byIndex bool) client.AudioSettingsDevice {
	if byIndex || countByName(devices, device.Name) > 1 {
		return client.NewIntAudioSettingsDevice(device.Index)
	}
	return client.NewStringAudioSettingsDevice(device.Name)
}

func countByName(devices []client.AudioDeviceInfo, name string) int {
	count := 0
	for _, device := range devices {
		if device.Name == name {
			count++
		}
	}
	return count
}

func areaChoices(areas []client.AreaInfo) []choice {
	choices := make([]choice, 0, len(areas))
	for index, area := range areas {
		label := area.Name
		if area.Active {
			label += "  (streaming)"
		}
		choices = append(choices, choice{Label: label, Value: index})
	}
	return choices
}

func deviceChoices(devices []client.AudioDeviceInfo) []choice {
	choices := make([]choice, 0, len(devices))
	for index, device := range devices {
		label := fmt.Sprintf("%s  --  %s", device.Name, device.HostAPI)
		if device.IsDefault {
			label += "  (default)"
		}
		choices = append(choices, choice{Label: label, Value: index})
	}
	return choices
}

func indexLabel(device client.AudioDeviceInfo) string {
	if device.IsDefault {
		return strconv.Itoa(device.Index) + " *"
	}
	return strconv.Itoa(device.Index)
}

func streaming(active bool) string {
	if active {
		return "yes"
	}
	return "no"
}

func yesNo(value bool) string {
	if value {
		return "yes"
	}
	return "no"
}
