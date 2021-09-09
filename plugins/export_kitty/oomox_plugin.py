# -*- coding: utf-8 -*-
import re
import os

from oomox_gui.i18n import _
from oomox_gui.plugin_api import OomoxImportPlugin, OomoxExportPlugin
from oomox_gui.export_common import ExportDialog
from oomox_gui.terminal import (
    get_lightness, natural_sort,
)
from oomox_gui.plugin_api import OomoxExportPlugin
from oomox_gui.terminal import generate_xrdb_theme_from_oomox
from oomox_gui.color import (
    mix_theme_colors, hex_darker, color_list_from_hex, int_list_from_hex,
)
from oomox_gui.config import USER_CONFIG_DIR

# Enable Base16 export if pystache and yaml are installed:
try:
    import pystache  # noqa  pylint: disable=unused-import
    import yaml  # noqa  pylint: disable=unused-import
except ImportError:
    # @TODO: replace to error dialog:
    print(
        "!! WARNING !! `pystache` and `python-yaml` need to be installed "
        "for exporting Base16 themes"
    )

    class PluginBase(OomoxImportPlugin):  # pylint: disable=abstract-method
        pass
else:
    class PluginBase(OomoxImportPlugin, OomoxExportPlugin):  # type: ignore  # pylint: disable=abstract-method
        pass

PLUGIN_DIR = os.path.dirname(os.path.realpath(__file__))
USER_BASE16_TEMPLATES_DIR = os.path.join(
    PLUGIN_DIR, "templates/"
)

OOMOX_TO_BASE16_TRANSLATION = {
    "TERMINAL_BACKGROUND": "base0H",
    "TERMINAL_FOREGROUND": "base0G",

    "TERMINAL_COLOR0": "base00",
    "TERMINAL_COLOR1": "base01",
    "TERMINAL_COLOR2": "base02",
    "TERMINAL_COLOR3": "base03",
    "TERMINAL_COLOR4": "base04",
    "TERMINAL_COLOR5": "base05",
    "TERMINAL_COLOR6": "base06",
    "TERMINAL_COLOR7": "base07",

    "TERMINAL_COLOR8": "base08",
    "TERMINAL_COLOR9": "base09",
    "TERMINAL_COLOR10": "base0A",
    "TERMINAL_COLOR11": "base0B",
    "TERMINAL_COLOR12": "base0C",
    "TERMINAL_COLOR13": "base0D",
    "TERMINAL_COLOR14": "base0E",
    "TERMINAL_COLOR15": "base0F",
}

def convert_oomox_to_base16(theme_name, colorscheme):
    base16_theme = {}

    base16_theme["scheme-name"] = base16_theme["scheme-author"] = \
        theme_name
    base16_theme["scheme-slug"] = base16_theme["scheme-name"].split('/')[-1].lower()

    for oomox_key, base16_key in OOMOX_TO_BASE16_TRANSLATION.items():
        base16_theme[base16_key] = colorscheme[oomox_key]

    return base16_theme

def convert_base16_to_template_data(base16_theme):
    base16_data = {}
    for key, value in base16_theme.items():
        if not key.startswith('base'):
            base16_data[key] = value
            continue

        hex_key = key + '-hex'
        base16_data[hex_key] = value
        base16_data[hex_key + '-r'], \
            base16_data[hex_key + '-g'], \
            base16_data[hex_key + '-b'] = \
            color_list_from_hex(value)

        rgb_key = key + '-rgb'
        base16_data[rgb_key + '-r'], \
            base16_data[rgb_key + '-g'], \
            base16_data[rgb_key + '-b'] = \
            int_list_from_hex(value)

        dec_key = key + '-dec'
        base16_data[dec_key + '-r'], \
            base16_data[dec_key + '-g'], \
            base16_data[dec_key + '-b'] = \
            [
                channel/255 for channel in int_list_from_hex(value)
            ]
    return base16_data

def render_base16_template(template_path, base16_theme):
    with open(template_path) as template_file:
        template = template_file.read()
    base16_data = convert_base16_to_template_data(base16_theme)
    result = pystache.render(template, base16_data)
    return result

class KittyExportDialog(ExportDialog):

    def _get_app_variant_template_path(self):
        return os.path.join(
            USER_BASE16_TEMPLATES_DIR, 'default.mustache'
        )

    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            headline=_("Terminal Colorscheme"),
            height=440,
            **kwargs
        )
        self.label.set_text(_('Paste this colorscheme to your ~/.config/alacritty/alacritty.yml:'))
        self.scrolled_window.show_all()
        try:
            # RENDER
            base16_theme = convert_oomox_to_base16(self.theme_name, self.colorscheme)
            template_path = self._get_app_variant_template_path()
            alacritty_theme = render_base16_template(template_path, base16_theme)
        except Exception as exc:
            self.set_text(exc)
            self.show_error()
        else:
            self.set_text(alacritty_theme)


class Plugin(OomoxExportPlugin):

    name = 'alacritty'

    display_name = _('Alacritty')
    shortcut = "<Primary>X"
    export_text = _("Export _Alacritty theme…")
    export_dialog = KittyExportDialog
