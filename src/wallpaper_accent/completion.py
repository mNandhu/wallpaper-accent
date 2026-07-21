"""`completion bash|zsh`: emit a shell completion script.

Component and knob names are baked into the script at generation time (from
`components.REGISTRY` / `config.KNOBS`), so re-source it after adding a
component or knob:  source <(wallpaper-accent completion zsh)
"""
from __future__ import annotations

from . import config
from .components import REGISTRY

_COMPONENTS = " ".join(REGISTRY)
_KNOBS = " ".join(config.KNOBS)
_SCHEMES = " ".join(config.SCHEMES)
_CONFIG_ACTIONS = "list get set unset edit"
_THEME_FLAGS = ("--force --no-reload --print --show --image --only --skip "
                "--undo --dark --light")


def _bash() -> str:
    return f"""\
# wallpaper-accent bash completion.
#   echo 'source <(wallpaper-accent completion bash)' >> ~/.bashrc
_wallpaper_accent() {{
    local cur prev words cword
    _init_completion || return
    local subcommands="{{{{SUBCOMMANDS}}}}"
    local components="{_COMPONENTS}"
    local knobs="{_KNOBS}"
    local schemes="{_SCHEMES}"
    local config_actions="{_CONFIG_ACTIONS}"

    if [[ $cword -eq 1 ]]; then
        COMPREPLY=($(compgen -W "$subcommands" -- "$cur"))
        return
    fi
    case "${{words[1]}}" in
        theme)
            case "$prev" in
                --only|--skip) COMPREPLY=($(compgen -W "$components" -- "$cur")); return ;;
                --image) COMPREPLY=($(compgen -f -- "$cur")); return ;;
            esac
            COMPREPLY=($(compgen -W "{_THEME_FLAGS}" -- "$cur"))
            ;;
        preview) COMPREPLY=($(compgen -f -- "$cur")) ;;
        completion) COMPREPLY=($(compgen -W "bash zsh" -- "$cur")) ;;
        config)
            if [[ $cword -eq 2 ]]; then
                COMPREPLY=($(compgen -W "$config_actions" -- "$cur"))
            elif [[ $cword -eq 3 && "${{words[2]}}" != "list" && "${{words[2]}}" != "edit" ]]; then
                COMPREPLY=($(compgen -W "$knobs" -- "$cur"))
            elif [[ $cword -eq 4 && "${{words[2]}}" == "set" && "${{words[3]}}" == "scheme" ]]; then
                COMPREPLY=($(compgen -W "$schemes" -- "$cur"))
            fi
            ;;
    esac
}}
complete -F _wallpaper_accent wallpaper-accent
"""


def _zsh() -> str:
    return f"""\
#compdef wallpaper-accent
# wallpaper-accent zsh completion.
#   echo 'source <(wallpaper-accent completion zsh)' >> ~/.zshrc
_wallpaper_accent() {{
    local -a subcommands components knobs schemes config_actions
    subcommands=({{{{SUBCOMMANDS}}}})
    components=({_COMPONENTS})
    knobs=({_KNOBS})
    schemes=({_SCHEMES})
    config_actions=({_CONFIG_ACTIONS})

    if (( CURRENT == 2 )); then
        _describe 'command' subcommands
        return
    fi
    case "${{words[2]}}" in
        theme)
            case "${{words[CURRENT-1]}}" in
                --only|--skip) _describe 'component' components; return ;;
                --image) _files; return ;;
            esac
            _values 'flag' {_THEME_FLAGS}
            ;;
        preview) _files ;;
        completion) _values 'shell' bash zsh ;;
        config)
            if (( CURRENT == 3 )); then
                _describe 'action' config_actions
            elif (( CURRENT == 4 )) && [[ "${{words[3]}}" != list && "${{words[3]}}" != edit ]]; then
                _describe 'knob' knobs
            elif (( CURRENT == 5 )) && [[ "${{words[3]}}" == set && "${{words[4]}}" == scheme ]]; then
                _describe 'scheme' schemes
            fi
            ;;
    esac
}}
compdef _wallpaper_accent wallpaper-accent
"""


def render(shell: str) -> str:
    if shell not in ("bash", "zsh"):
        raise ValueError(f"unsupported shell {shell!r} (bash, zsh)")
    from .cli import SUBCOMMANDS
    subcommands = " ".join(sorted(SUBCOMMANDS))
    script = _bash() if shell == "bash" else _zsh()
    return script.replace("{{SUBCOMMANDS}}", subcommands)
