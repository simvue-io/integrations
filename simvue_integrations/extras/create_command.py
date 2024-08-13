import typing
# TODO: This is copied from run.py in python-api, could just make it a function there and call that instead of repeating here

def format_command_env_vars(cmd_kwargs: typing.Dict[str, typing.Union[bool, str, float, int]]):
    """Create a list of strings representing environment variables to a command from a dictionary of kwarg key:value pairs

    Parameters
    ----------
    cmd_kwargs : typing.Dict[str, typing.Union[bool, str, float, int]]
        The variables to pass to the command, in a dictionary
    """
    cmd_list = []
    for kwarg, val in cmd_kwargs.items():
        _quoted_val: str = f'"{val}"'
        if len(kwarg) == 1:
            if isinstance(val, bool) and val:
                cmd_list += [f"-{kwarg}"]
            else:
                cmd_list += [f"-{kwarg}{(' '+ _quoted_val) if val else ''}"]
        else:
            kwarg = kwarg.replace("_", "-")
            if isinstance(val, bool) and val:
                cmd_list += [f"--{kwarg}"]
            else:
                cmd_list += [f"--{kwarg}{(' '+_quoted_val) if val else ''}"]
                
    return cmd_list