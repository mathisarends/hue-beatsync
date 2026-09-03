package commands

import (
	"fmt"

	"github.com/mathisarends/hue-beatsync/cli/internal/client"
)

type startCommand struct {
	Settings settingsFlags `embed:""`
}

type stopCommand struct{}

type statusCommand struct{}

func (command startCommand) Run(runtime *Runtime) error {
	request, _, err := command.Settings.request()
	if err != nil {
		return err
	}
	result, err := send[*client.StatusResponse](
		runtime, "start", (*client.Client).StartSync, request)
	if err != nil {
		return err
	}
	return runtime.output(result, func() error {
		if err := writeLines(runtime.stdout, fmt.Sprintf("Streaming to %s.", areaLabel(result))); err != nil {
			return err
		}
		return writeNext(runtime.stdout, "lichtorgel stop")
	})
}

func (stopCommand) Run(runtime *Runtime) error {
	result, err := fetch[*client.StatusResponse](runtime, "stop", (*client.Client).StopSync)
	if err != nil {
		return err
	}
	return runtime.output(result, func() error {
		return writeLines(runtime.stdout, "Stopped. The lights stay where they are.")
	})
}

func (statusCommand) Run(runtime *Runtime) error {
	result, err := fetch[*client.StatusResponse](runtime, "status", (*client.Client).GetStatus)
	if err != nil {
		return err
	}
	return runtime.output(result, func() error {
		if !result.Running {
			if err := writeLines(runtime.stdout, "Not streaming."); err != nil {
				return err
			}
			return writeNext(runtime.stdout, "lichtorgel start")
		}
		if err := writeLines(runtime.stdout, fmt.Sprintf("Streaming to %s.", areaLabel(result))); err != nil {
			return err
		}
		return writeNext(runtime.stdout, "lichtorgel stop")
	})
}

func areaLabel(status *client.StatusResponse) string {
	if area, ok := status.Area.Get(); ok && area != "" {
		return fmt.Sprintf("%q", area)
	}
	return "the configured area"
}
