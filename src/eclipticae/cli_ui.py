"""Interactive and fallback CLI input helpers for wizard flows."""

from __future__ import annotations

import sys
from contextlib import suppress
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import click
import typer

if TYPE_CHECKING:
    from prompt_toolkit.key_binding.key_bindings import KeyBindingsBase

_BACK_SENTINEL = "__back__"

questionary_module: Any | None = None
with suppress(ImportError):  # pragma: no branch - optional runtime UX dependency
    import questionary as questionary_module

prompt_toolkit_prompt: Any | None = None
PromptKeyBindings: Any | None = None
with suppress(ImportError):  # pragma: no branch - optional runtime UX dependency
    from prompt_toolkit import prompt as prompt_toolkit_prompt
    from prompt_toolkit.key_binding import KeyBindings as PromptKeyBindings


@dataclass(frozen=True, slots=True)
class _MenuOption:
    key: str
    label: str
    detail: str = ""


class _WizardBackError(Exception):
    """Raised when the user requests to navigate back in wizard flow."""


def _ui_select(
    title: str,
    *,
    options: list[_MenuOption],
    default_key: str,
    allow_back: bool = False,
) -> str:
    if _use_rich_wizard():
        qmod, choice_class = _require_questionary()
        rendered_choices = []
        for option in options:
            detail = f" - {option.detail}" if option.detail else ""
            rendered_choices.append(
                choice_class(
                    title=f"{option.label}{detail}",
                    value=option.key,
                ),
            )
        if allow_back:
            rendered_choices.append(choice_class(title="Back", value=_BACK_SENTINEL))
        try:
            answer = qmod.select(
                title,
                choices=rendered_choices,
                default=default_key,
                qmark=">",
                pointer="> ",
            ).ask()
        except KeyboardInterrupt as exc:
            if allow_back:
                raise _WizardBackError from exc
            raise typer.Abort from exc
        if answer is None:
            if allow_back:
                raise _WizardBackError
            raise typer.Abort
        if allow_back and answer == _BACK_SENTINEL:
            raise _WizardBackError
        return str(answer)
    return _ask_menu(
        title,
        options=options,
        default_key=default_key,
        allow_back=allow_back,
    )


def _ui_text(prompt: str, *, default: str, allow_back: bool = False) -> str:
    prompt_text = prompt
    if _use_rich_wizard() and allow_back and _supports_rich_escape_back():
        return _ui_text_rich_with_escape_back(prompt_text, default=default)
    if _use_rich_wizard():
        return _ui_text_rich(prompt_text, default=default, allow_back=allow_back)
    return _ui_text_plain(prompt_text, default=default, allow_back=allow_back)


def _ui_text_rich_with_escape_back(prompt_text: str, *, default: str) -> str:
    key_bindings = _build_rich_back_key_bindings()
    if prompt_toolkit_prompt is None:
        msg = "prompt_toolkit is required for rich wizard escape-back support."
        raise RuntimeError(msg)
    try:
        answer = prompt_toolkit_prompt(
            f"{prompt_text}: ",
            default=default,
            key_bindings=key_bindings,
        )
    except click.Abort as exc:
        raise _WizardBackError from exc
    if answer == _BACK_SENTINEL:
        raise _WizardBackError
    return str(answer)


def _ui_text_rich(prompt_text: str, *, default: str, allow_back: bool) -> str:
    qmod, _ = _require_questionary()
    try:
        answer = qmod.text(prompt_text, default=default, qmark=">").ask()
    except (KeyboardInterrupt, click.Abort) as exc:
        if allow_back:
            raise _WizardBackError from exc
        raise typer.Abort from exc
    if answer is None:
        if allow_back:
            raise _WizardBackError
        raise typer.Abort
    return str(answer)


def _ui_text_plain(prompt_text: str, *, default: str, allow_back: bool) -> str:
    try:
        return str(typer.prompt(prompt_text, default=default))
    except click.Abort as exc:
        if allow_back:
            raise _WizardBackError from exc
        raise


def _ui_confirm(prompt: str, *, default: bool, allow_back: bool = False) -> bool:
    if _use_rich_wizard():
        qmod, choice_class = _require_questionary()
        yes_choice = choice_class(title="Yes", value=True)
        no_choice = choice_class(title="No", value=False)
        choices = [yes_choice, no_choice] if default else [no_choice, yes_choice]
        if allow_back:
            choices.append(choice_class(title="Back", value=_BACK_SENTINEL))
        try:
            answer = qmod.select(
                prompt,
                choices=choices,
                default=default,
                qmark=">",
                pointer="> ",
            ).ask()
        except (KeyboardInterrupt, click.Abort) as exc:
            if allow_back:
                raise _WizardBackError from exc
            raise typer.Abort from exc
        if answer is None:
            if allow_back:
                raise _WizardBackError
            raise typer.Abort
        if allow_back and answer == _BACK_SENTINEL:
            raise _WizardBackError
        return bool(answer)
    yes_first = default
    result = _ask_menu(
        prompt,
        options=(
            [_MenuOption("yes", "Yes"), _MenuOption("no", "No")]
            if yes_first
            else [_MenuOption("no", "No"), _MenuOption("yes", "Yes")]
        ),
        default_key="yes" if default else "no",
        allow_back=allow_back,
    )
    return result == "yes"


def _ui_int(prompt: str, *, default: int, allow_back: bool = False) -> int:
    while True:
        answer = _ui_text(prompt, default=str(default), allow_back=allow_back).strip()
        try:
            return int(answer)
        except ValueError:
            typer.echo("Please enter a whole number.")


def _ui_float(
    prompt: str,
    *,
    default: float | None = None,
    allow_back: bool = False,
) -> float:
    seed = "" if default is None else str(default)
    while True:
        answer = _ui_text(prompt, default=seed, allow_back=allow_back).strip()
        try:
            return float(answer)
        except ValueError:
            typer.echo("Please enter a numeric value.")


def _use_rich_wizard() -> bool:
    return bool(
        questionary_module is not None and sys.stdin.isatty() and sys.stdout.isatty(),
    )


def _require_questionary() -> tuple[Any, Any]:
    if questionary_module is None:
        msg = "questionary is required for rich wizard mode."
        raise RuntimeError(msg)
    return questionary_module, questionary_module.Choice


def _supports_rich_escape_back() -> bool:
    return prompt_toolkit_prompt is not None and PromptKeyBindings is not None


def _build_rich_back_key_bindings() -> KeyBindingsBase:
    if PromptKeyBindings is None:
        msg = "prompt_toolkit is required for rich wizard escape-back support."
        raise RuntimeError(msg)
    key_bindings: KeyBindingsBase = PromptKeyBindings()

    @key_bindings.add("escape")
    def _on_escape(event: object) -> None:
        app = getattr(event, "app", None)
        if app is not None:
            app.exit(result=_BACK_SENTINEL)

    return key_bindings


def _ask_menu(
    title: str,
    *,
    options: list[_MenuOption],
    default_key: str,
    allow_back: bool = False,
) -> str:
    if not options:
        msg = "Menu options cannot be empty."
        raise ValueError(msg)

    default_index = 1
    for index, option in enumerate(options, start=1):
        if option.key == default_key:
            default_index = index
            break

    while True:
        typer.echo(title)
        if allow_back:
            typer.echo("  0. Back")
        for index, option in enumerate(options, start=1):
            detail = f" - {option.detail}" if option.detail else ""
            typer.echo(f"  {index}. {option.label}{detail}")
        try:
            raw = str(
                typer.prompt(
                    f"Choose [1-{len(options)}]",
                    default=str(default_index),
                ),
            ).strip()
        except click.Abort as exc:
            if allow_back:
                raise _WizardBackError from exc
            raise
        selected_key = _parse_menu_choice(raw, options=options, allow_back=allow_back)
        if selected_key is not None:
            return selected_key
        typer.echo("Invalid choice. Use an option number or name.")


def _parse_menu_choice(
    raw: str,
    *,
    options: list[_MenuOption],
    allow_back: bool,
) -> str | None:
    normalized = raw.lower()
    if allow_back and normalized == "0":
        raise _WizardBackError
    if raw.isdigit():
        numeric_index = int(raw)
        if 1 <= numeric_index <= len(options):
            return options[numeric_index - 1].key
    for option in options:
        if normalized in {option.key.lower(), option.label.lower()}:
            return option.key
    return None
