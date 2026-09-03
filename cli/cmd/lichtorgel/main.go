package main

import (
	"context"
	"os"
	"os/signal"

	"github.com/mathisarends/hue-beatsync/cli/internal/commands"
)

var version = "dev"

func main() {
	commands.Version = version
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt)
	defer stop()
	os.Exit(commands.Run(ctx, os.Args[1:], os.Stdin, os.Stdout, os.Stderr))
}
