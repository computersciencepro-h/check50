import os
import tempfile
from pathlib import Path
import xml.etree.cElementTree as ET

from .api import run, log, Failure
from . import internal

CC = "clang"
CFLAGS = "-std=c11 -ggdb3 -lcs50 -lm"


def compile(file_name, exe_name=None, compiler=CC, compilers_flags=CFLAGS):
    f"""
    compile file_name to exe_name (file_name minus .c by default)
    uses compiler: {CC} with compilers_flags: {CFLAGS} by default
    """
    if exe_name is None and file_name.endswith(".c"):
        exe_name = file_name.split(".c")[0]

    out_flag = f"-o {exe_name}" if exe_name is not None else ""

    run(f"{compiler} {file_name} {out_flag} {compilers_flags}").exit(0)


def valgrind(command):
    """run command with valgrind, checks for valgrind errors at the end of the check"""
    xml_file = tempfile.NamedTemporaryFile()
    internal.register.after(lambda: _check_valgrind(xml_file))

    # ideally we'd like for this whole command not to be logged.
    return run(f"valgrind --show-leak-kinds=all --xml=yes --xml-file={xml_file.name} -- {command}")


def _check_valgrind(xml_file):
    """Log and report any errors encountered by valgrind"""
    log("checking for valgrind errors... ")

    # Load XML file created by valgrind
    xml = ET.ElementTree(file=xml_file)

    # Ensure that we don't get duplicate error messages.
    reported = set()
    for error in xml.iterfind("error"):
        # Type of error valgrind encountered
        kind = error.find("kind").text

        # Valgrind's error message
        what = error.find("xwhat/text" if kind.startswith("Leak_") else "what").text

        # Error message that we will report
        msg = ["\t", what]

        # Find first stack frame within student's code.
        for frame in error.iterfind("stack/frame"):
            obj = frame.find("obj")
            if obj is not None and internal.run_dir in Path(obj.text).parents:
                file, line = frame.find("file"), frame.find("line")
                if file is not None and line is not None:
                    msg.append(f": (file: {file.text}, line: {line.text})")
                break

        msg = "".join(msg)
        if msg not in reported:
            log(msg)
            reported.add(msg)

    # Only raise exception if we encountered errors.
    if reported:
        raise Failure("valgrind tests failed; rerun with --log for more information.")
