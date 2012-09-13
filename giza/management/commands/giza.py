#!/usr/bin/env python
# -*- coding:Utf-8 -*-

"""
When you add and remove modules (but not classes and functions)
from the project you'll need to re-run this script to generate
the docs/auto_modules.rst file again
"""

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import os
import re


def get_module_dirpath(module_name):
    return os.path.realpath(os.path.dirname(__import__(module_name).__file__))

PROJECT_ROOT = get_module_dirpath(os.environ['DJANGO_SETTINGS_MODULE'])

# http://sphinx.pocoo.org/rest.html#sections
# I've numbered these in HTML style from 1 to 6
SPHINX_SECTIONS = {
    1: ('#', True),
    2: ('*', True),
    3: ('=', False),
    4: ('-', False),
    5: ('^', False),
    6: ('"', False),
}
def sphinx_heading(level, title, trailing_breaks=1):
    symbol_line = SPHINX_SECTIONS[level][0] * len(title)
    lines = []
    if SPHINX_SECTIONS[level][1]:
        # 'overline'
        lines.append(symbol_line)
    lines.append(title)
    lines.append(symbol_line)
    lines.extend([""] * trailing_breaks)
    return lines


class ModulesWriter(object):
    """
    Generates an auto_modules.rst file referencing all the app's automodules
    """

    def __init__(self, filename, doc_title, automodule_options, excluded_modules, excluded_apps):
        self.filename = filename
        self.doc_title = doc_title
        self.automodule_options = automodule_options
        self.excluded_modules = excluded_modules
        self.excluded_apps = excluded_apps# we'll also accept wildcard, eg "django.contrib.*"

        self.lines = self.make_head(self.doc_title)
        self.internal_lines = []
        self.external_lines = []

    def write(self):
        """
        Write the created list in the new file
        """
        self.add_section("Project Apps", self.internal_lines)
        self.add_section("3rd Party Apps", self.external_lines)

        f = open(self.filename, "w+")
        f.writelines("%s\n" % l for l in self.lines)
        f.close()

    def add_section(self, title, lines, heading_level=2):
        self.lines.append("")
        self.lines.extend(sphinx_heading(heading_level, title))
        self.lines.extend(lines)

    def add_to_toc(self, master_doc_path):
        """
        Verifies that a "auto_modules" file is in the toctree, and appends it
        otherwise.
   
        Note:
            This method writes to the file at master_doc_path!
        """
        master_doc = open(master_doc_path, "r")
        master_doc_lines = master_doc.readlines()

        if not self.filename in "".join(master_doc_lines):
            # append the new file name to the index.rst
            for i, line in enumerate(master_doc_lines):
                if ":maxdepth: 2" in line:
                    master_doc_lines.insert(i + 2, "    %s\n" % self.filename)
                    break
        master_doc = open(master_doc_path, "w")
        master_doc.writelines(master_doc_lines)
        master_doc.close()

    def make_head(self, title):
        """
        Header lines for the generated document (eg comment, page title etc)
        """
        symbol_line = "#" * len(title)
        return [
            ".. This file is auto-generated by the generate_autodoc.py script",
            "   (When you add and remove modules from the project you'll need to",
            "   re-run the script to generate this file again)",
            "",
        ] + sphinx_heading(1, title, trailing_breaks=2)

    def _should_exclude(self, name):
        for pattern in self.excluded_apps:
            if name == pattern or (pattern.endswith('*') and name.startswith(pattern[:-1])):
                return True
        return False

    def add_apps(self, search_apps):
        """
        Add all the given apps to the auto_modules file
        """
        for name in search_apps:
            if not self._should_exclude(name):
                self.add_app(App(name, self.excluded_modules))

    def add_app(self, app):
        """
        Add automodule directive lines for each of the modules in `app`
        """
        # title
        template = sphinx_heading(3, app.name)

        if not app.modules:
            print "no modules in app %s" % app.name
            return

        # Write an automodule for each of app's modules
        for module in app.modules:
            # title:
            template.extend(sphinx_heading(4, module))
            # automodule directive:
            template.append(".. automodule:: %s.%s" % (app.name, module))
            # options for automodule directive:
            template.extend(map(lambda o: "    :%s:" % o, self.automodule_options))
            template.append("")
        if app.is_internal:
            self.internal_lines.extend(template)
        else:
            self.external_lines.extend(template)


class App(object):
    """
    Handlings processing a django app with its name and the list of python files it contains
    """

    def __init__(self, name, excluded_modules):
        self.name = name
        self.excluded_modules = excluded_modules

        self.is_internal = os.path.exists(os.path.join(PROJECT_ROOT, *name.split('.')))
        self.modules = self.get_modules()

    def get_modules(self):
        """Scan the repository for any python files"""
        module_path = get_module_dirpath(self.name)
        modules = []
        for name in os.listdir(module_path):
            if name not in self.excluded_modules and name.endswith(".py"):
               modules.append(name.split(".py")[0])
        # Remove all irrelevant modules. A module is relevant if he
        # contains a function or class
        not_relevant = []
        for module in modules:
            f_module = open(os.path.join(module_path, "%s.py" % module), "r")
            content = f_module.read()
            f_module.close()
            # TODO: can we introspect this instead??
            keywords = ["def", "class"]
            relevant = sum([value in content for value in keywords])
            if not relevant:
                not_relevant.append(module)
                print "%s.%s not relevant, removed" % (self.name, module)
        for module in not_relevant:
            modules.remove(module)
        return modules


class Command(BaseCommand):
    args = '<docs_root (optional)>'
    help = 'Generates a sphinx doc file referencing all modules in INSTALLED_APPS'

    def handle(self, *args, **options):
        # Define some variables
        try:
            docs_root = os.path.join(PROJECT_ROOT, args[0])
        except IndexError:
            docs_root = getattr(settings, "GIZA_DOCS_ROOT", os.path.join(PROJECT_ROOT, "docs"))

        master_doc = getattr(settings, "GIZA_INDEX_DOC", "index.rst")
        filename = getattr(settings, "GIZA_FILENAME", "auto_modules")
        doc_title = getattr(settings, "GIZA_DOC_TITLE", "Python modules")
        excluded_apps = getattr(settings, "GIZA_EXCLUDED_APPS", [
            'django.*',
            'giza',
        ])
        excluded_modules = getattr(settings, "GIZA_EXCLUDED_MODULES", [
            "__init__.py",
        ])
        automodule_options = getattr(settings, "GIZA_AUTOMODULE_OPTIONS", [
            "deprecated",
            "members",
            "private-members",
            "special-members",
            "show-inheritance",
        ])

        modules_writer = ModulesWriter(
            filename=os.path.join(docs_root, "%s.rst" % filename),
            doc_title=doc_title,
            automodule_options=automodule_options,
            excluded_modules=excluded_modules,
            excluded_apps=excluded_apps,
        )
        modules_writer.add_apps(settings.INSTALLED_APPS)
        modules_writer.add_to_toc(os.path.join(docs_root, master_doc))
        modules_writer.write()
