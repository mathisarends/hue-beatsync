import click


class FlexibleGroup(click.Group):
    def parse_args(self, context: click.Context, args: list[str]) -> list[str]:
        output_flags = {"--json", "--plain"}
        global_args = [argument for argument in args if argument in output_flags]
        command_args = [argument for argument in args if argument not in output_flags]
        return super().parse_args(context, global_args + command_args)
