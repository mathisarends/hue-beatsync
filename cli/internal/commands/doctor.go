package commands

import (
	"errors"
	"fmt"
	"strings"

	"github.com/mathisarends/hue-beatsync/cli/internal/client"
)

// The server has no doctor endpoint, so the report is assembled from the
// read-only routes it does have.
type doctorCommand struct{}

const (
	statusOK     = "ok"
	statusWarn   = "warn"
	statusFailed = "failed"
)

type checkResult struct {
	Name   string `json:"name"`
	Status string `json:"status"`
	Detail string `json:"detail,omitempty"`
}

type doctorReport struct {
	Status string        `json:"status"`
	Checks []checkResult `json:"checks"`
}

func (doctorCommand) Run(runtime *Runtime) error {
	report := doctorReport{Status: statusOK}
	add := func(name, status, detail string) {
		report.Checks = append(report.Checks, checkResult{Name: name, Status: status, Detail: detail})
		if status == statusFailed {
			report.Status = statusFailed
		} else if status == statusWarn && report.Status == statusOK {
			report.Status = statusWarn
		}
	}

	status, err := fetch[*client.StatusResponse](runtime, "status", (*client.Client).GetStatus)
	if err != nil {
		add("server", statusFailed, detailOf(err))
		return runtime.doctorOutput(report)
	}
	add("server", statusOK, runtime.config.BaseURL)

	devices, err := listDevices(runtime)
	if err != nil {
		add("audio inputs", statusFailed, detailOf(err))
	} else {
		add("audio inputs", statusOK, fmt.Sprintf("%d available", len(devices)))
	}

	areas, err := listAreas(runtime)
	if err != nil {
		add("hue bridge", statusFailed, detailOf(err))
	} else {
		add("hue bridge", statusOK, fmt.Sprintf("%d entertainment area(s)", len(areas)))
	}

	defaults, err := fetch[*client.SyncSettings](runtime, "read defaults", (*client.Client).GetDefaults)
	if err != nil {
		add("saved settings", statusFailed, detailOf(err))
	} else {
		name, checkStatus, detail := savedAreaCheck(defaults, areas)
		add(name, checkStatus, detail)
		name, checkStatus, detail = savedDeviceCheck(defaults, devices)
		add(name, checkStatus, detail)
	}

	if status.Running {
		add("stream", statusOK, "running: "+areaLabel(status))
	} else {
		add("stream", statusOK, "idle")
	}
	return runtime.doctorOutput(report)
}

// The one setting with no fallback anywhere: a start without an area is
// rejected by the server.
func savedAreaCheck(defaults *client.SyncSettings, areas []client.AreaInfo) (string, string, string) {
	const name = "saved area"
	area, ok := defaults.Area.Get()
	if !ok || strings.TrimSpace(area) == "" {
		return name, statusFailed, "not set; run: lichtorgel area select"
	}
	if areas == nil {
		return name, statusOK, area
	}
	if _, err := matchArea(areas, area); err != nil {
		return name, statusFailed, fmt.Sprintf("%q is not among the bridge's areas", area)
	}
	return name, statusOK, area
}

func savedDeviceCheck(defaults *client.SyncSettings, devices []client.AudioDeviceInfo) (string, string, string) {
	const name = "saved audio input"
	audio, ok := defaults.Audio.Get()
	if !ok {
		return name, statusWarn, "not set; the backend's default input is used"
	}
	device, ok := describeDevice(audio.Device)
	if !ok {
		return name, statusWarn, "not set; the backend's default input is used"
	}
	if devices == nil {
		return name, statusOK, device
	}
	if _, err := matchDevice(devices, device); err != nil {
		return name, statusFailed, fmt.Sprintf("%q matches no audio input", device)
	}
	return name, statusOK, device
}

func (r *Runtime) doctorOutput(report doctorReport) error {
	err := r.output(report, func() error {
		rows := make([][]string, 0, len(report.Checks))
		for _, check := range report.Checks {
			rows = append(rows, []string{check.Status, check.Name, check.Detail})
		}
		if err := writeTable(r.stdout, nil, rows, emptyState{Message: "No checks reported."}); err != nil {
			return err
		}
		switch report.Status {
		case statusOK:
			return writeLines(r.stdout, "Everything a stream needs is in place.", "Next  lichtorgel start")
		case statusWarn:
			return writeLines(r.stdout, "Usable, but something is falling back to a default.")
		default:
			return writeLines(r.stdout, "Not ready to stream yet.")
		}
	})
	if err != nil {
		return err
	}
	if report.Status == statusFailed {
		// The report is the answer and has already been printed; only the exit
		// code is still owed, so nothing may be written a second time.
		return &exitCodeError{code: 1}
	}
	return nil
}

func detailOf(err error) string {
	normalized := normalizeError(err)
	var commandErr *commandError
	if errors.As(normalized, &commandErr) {
		return commandErr.Message
	}
	return normalized.Error()
}
