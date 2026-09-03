package commands

import (
	"context"

	"github.com/mathisarends/hue-beatsync/cli/internal/client"
)

// fetch connects, runs one operation, and narrows its response to the success
// variant. ogen models every documented status of an operation as its own
// type, so the returned union has to be narrowed before the payload is usable.
func fetch[Want, Res any](
	runtime *Runtime,
	operation string,
	invoke func(*client.Client, context.Context) (Res, error),
) (Want, error) {
	var zero Want
	apiClient, err := runtime.client()
	if err != nil {
		return zero, err
	}
	response, err := invoke(apiClient, runtime.ctx)
	if err != nil {
		return zero, err
	}
	result, ok := any(response).(Want)
	if !ok {
		return zero, apiFailure(operation, response)
	}
	return result, nil
}

func send[Want, Req, Res any](
	runtime *Runtime,
	operation string,
	invoke func(*client.Client, context.Context, Req) (Res, error),
	request Req,
) (Want, error) {
	return fetch[Want](runtime, operation, func(apiClient *client.Client, ctx context.Context) (Res, error) {
		return invoke(apiClient, ctx, request)
	})
}
