import subprocess


def sys_call(command, shell=True):
    return_code, output = 0, ''
    try:
        output = subprocess.check_output(
            command,
            stderr=subprocess.STDOUT,
            shell=shell
        )
    except subprocess.CalledProcessError as err:
        return_code, output = err.returncode, err.output
    return return_code, output