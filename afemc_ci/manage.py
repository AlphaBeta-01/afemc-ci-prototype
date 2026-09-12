#!/usr/bin/env python
"""Point d'entrée des commandes d'administration du projet AFEMC-CI."""
import os
import sys


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Django ne semble pas installé. Activez l'environnement virtuel "
            "puis exécutez : pip install -r requirements.txt"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
