"""GENESIS: the installer, repair and maintenance engine of Agent Guru.

Everything in this package imports only the standard library. It runs inside
the small frozen launcher before any of Agent Guru's own dependencies exist,
so an import of numpy, pydantic or httpx here would either fail on a fresh
machine or pull a large library into the installer. Work that needs the
installed application (loading a model, synthesising speech) runs in the
managed runtime through runtime_tasks.py, as a separate process.

The journal (journal.py) is the one record of what happened. The screens, the
command line, the reports and the tests read it; none of them keeps a status
of its own.
"""
