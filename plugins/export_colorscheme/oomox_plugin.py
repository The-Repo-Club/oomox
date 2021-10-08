# -*- coding: utf-8 -*-
import os
import subprocess
from typing import List, Dict

from gi.repository import Gtk, GLib

from oomox_gui.i18n import _
from oomox_gui.plugin_api import OomoxExportPlugin
from oomox_gui.export_common import FileBasedExportDialog
from oomox_gui.terminal import get_lightness
from oomox_gui.color import (
    mix_theme_colors, hex_darker, color_list_from_hex, int_list_from_hex,
)
from oomox_gui.export_common import ExportConfig
from oomox_gui.config import USER_CONFIG_DIR

# Enable ColorScheme export if pystache and yaml are installed:
try:
    import pystache  # noqa  pylint: disable=unused-import
    import yaml  # noqa  pylint: disable=unused-import
except ImportError:
    # @TODO: replace to error dialog:
    print(
        "!! WARNING !! `pystache` and `python-yaml` need to be installed "
        "for exporting ColorScheme themes"
    )
else:
    class PluginBase(OomoxExportPlugin):  # type: ignore  # pylint: disable=abstract-method
        pass


PLUGIN_DIR = os.path.dirname(os.path.realpath(__file__))
USER_COLORSCHEME_DIR = os.path.join(
    USER_CONFIG_DIR, "colorscheme/"
)
USER_COLORSCHEME_TEMPLATES_DIR = os.path.join(
    USER_COLORSCHEME_DIR, "templates/"
)


OOMOX_TO_COLORSCHEME_TRANSLATION = {
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


def yaml_load(content):
    return yaml.load(content, Loader=yaml.SafeLoader)


def convert_oomox_to_colorscheme(theme_name, colorscheme):
    colorscheme_theme = {}

    colorscheme_theme["scheme-name"] = colorscheme_theme["scheme-author"] = \
        theme_name
    colorscheme_theme["scheme-slug"] = colorscheme_theme["scheme-name"].split('/')[-1].lower()

    for oomox_key, colorscheme_key in OOMOX_TO_COLORSCHEME_TRANSLATION.items():
        colorscheme_theme[colorscheme_key] = colorscheme[oomox_key]

    return colorscheme_theme


def convert_colorscheme_to_template_data(colorscheme_theme):
    colorscheme_data = {}
    for key, value in colorscheme_theme.items():
        if not key.startswith('base'):
            colorscheme_data[key] = value
            continue

        hex_key = key + '-hex'
        colorscheme_data[hex_key] = value
        colorscheme_data[hex_key + '-r'], \
            colorscheme_data[hex_key + '-g'], \
            colorscheme_data[hex_key + '-b'] = \
            color_list_from_hex(value)

        rgb_key = key + '-rgb'
        colorscheme_data[rgb_key + '-r'], \
            colorscheme_data[rgb_key + '-g'], \
            colorscheme_data[rgb_key + '-b'] = \
            int_list_from_hex(value)

        dec_key = key + '-dec'
        colorscheme_data[dec_key + '-r'], \
            colorscheme_data[dec_key + '-g'], \
            colorscheme_data[dec_key + '-b'] = \
            [
                channel/255 for channel in int_list_from_hex(value)
            ]
    return colorscheme_data


def render_colorscheme_template(template_path, colorscheme_theme):
    with open(template_path) as template_file:
        template = template_file.read()
    colorscheme_data = convert_colorscheme_to_template_data(colorscheme_theme)
    result = pystache.render(template, colorscheme_data)
    return result


class ConfigKeys:
    last_app = 'last_app'
    last_variant = 'last_variant'


class ColorSchemeTemplate:
    name: str
    path: str

    def __init__(self, path: str):
        self.path = path
        self.name = os.path.basename(path)

    @property
    def template_dir(self):
        return os.path.join(
            self.path, 'templates',
        )

    def get_config(self):
        config_path = os.path.join(
            self.template_dir, 'config.yaml'
        )
        with open(config_path) as config_file:
            config = yaml_load(config_file.read())
        return config


class ColorSchemeExportDialog(FileBasedExportDialog):

    available_apps: Dict[str, ColorSchemeTemplate] = {}
    current_app: ColorSchemeTemplate
    available_variants: List[str]
    current_variant = None
    templates_homepages: Dict[str, str]

    _variants_changed_signal = None

    @property
    def _sorted_appnames(self):
        return sorted(self.available_apps.keys())

    def _get_app_variant_template_path(self):
        return os.path.join(
            self.current_app.template_dir, self.current_variant + '.mustache'
        )

    def colorscheme_stuff(self):
        # NAME
        colorscheme_theme = convert_oomox_to_colorscheme(self.theme_name, self.colorscheme)
        variant_config = self.current_app.get_config()[self.current_variant]
        output_name = '{}{}'.format(
            colorscheme_theme['scheme-slug'], variant_config['extension']
        )
        output_path = os.path.join(
            variant_config['output'], output_name
        )
        print(output_path)

        # RENDER
        template_path = self._get_app_variant_template_path()
        result = render_colorscheme_template(template_path, colorscheme_theme)

        # OUTPUT
        self.set_text(result)
        self.show_text()

        self.export_config.save()

    def _set_variant(self, variant):
        self.current_variant = \
            self.export_config[ConfigKeys.last_variant] = \
            variant

    def _on_app_changed(self, apps_dropdown):
        self.current_app = \
            self.available_apps[self._sorted_appnames[apps_dropdown.get_active()]]
        self.export_config[ConfigKeys.last_app] = self.current_app.name

        config = self.current_app.get_config()
        self.available_variants = list(config.keys())
        if self._variants_changed_signal:
            self._variants_dropdown.disconnect(self._variants_changed_signal)
        self._variants_store.clear()
        for variant in self.available_variants:
            self._variants_store.append([variant, ])
        self._variants_changed_signal = \
            self._variants_dropdown.connect("changed", self._on_variant_changed)

        variant = self.current_variant or self.export_config[ConfigKeys.last_variant]
        if not variant or variant not in self.available_variants:
            variant = self.available_variants[0]
        self._set_variant(variant)

        self._variants_dropdown.set_active(self.available_variants.index(self.current_variant))

        url = self.templates_homepages.get(self.current_app.name)
        self._homepage_button.set_sensitive(bool(url))

    def _init_apps_dropdown(self):
        options_store = Gtk.ListStore(str)
        for app_name in self._sorted_appnames:
            options_store.append([app_name, ])
        self._apps_dropdown = Gtk.ComboBox.new_with_model(options_store)
        renderer_text = Gtk.CellRendererText()
        self._apps_dropdown.pack_start(renderer_text, True)
        self._apps_dropdown.add_attribute(renderer_text, "text", 0)

        self._apps_dropdown.connect("changed", self._on_app_changed)
        GLib.idle_add(
            self._apps_dropdown.set_active,
            (self._sorted_appnames.index(self.current_app.name))
        )

    def _on_variant_changed(self, variants_dropdown):
        variant = self.available_variants[variants_dropdown.get_active()]
        self._set_variant(variant)
        self.colorscheme_stuff()

    def _init_variants_dropdown(self):
        self._variants_store = Gtk.ListStore(str)
        self._variants_dropdown = Gtk.ComboBox.new_with_model(self._variants_store)
        renderer_text = Gtk.CellRendererText()
        self._variants_dropdown.pack_start(renderer_text, True)
        self._variants_dropdown.add_attribute(renderer_text, "text", 0)

    def _on_homepage_button(self, _button):
        url = self.templates_homepages[self.current_app.name]
        cmd = ["xdg-open", url, ]
        subprocess.Popen(cmd)

    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            height=800, width=800,
            headline=_("ColorScheme Export Options…"),
            **kwargs
        )
        self.label.set_text(_("Choose export options below and copy-paste the result."))
        self.export_config = ExportConfig(
            config_name='colorscheme',
            default_config={
                ConfigKeys.last_variant: None,
                ConfigKeys.last_app: None,
            }
        )

        if not os.path.exists(USER_COLORSCHEME_TEMPLATES_DIR):
            os.makedirs(USER_COLORSCHEME_TEMPLATES_DIR)

        system_templates_dir = os.path.abspath(
            os.path.join(PLUGIN_DIR, 'templates')
        )
        templates_index_path = system_templates_dir + '.yaml'
        with open(templates_index_path) as templates_index_file:
            self.templates_homepages = yaml_load(templates_index_file.read())

        # APPS
        for templates_dir in (system_templates_dir, USER_COLORSCHEME_TEMPLATES_DIR):
            for template_name in os.listdir(templates_dir):
                template = ColorSchemeTemplate(path=os.path.join(templates_dir, template_name))
                self.available_apps[template.name] = template
        current_app_name = self.export_config[ConfigKeys.last_app]
        if not current_app_name or current_app_name not in self.available_apps:
            current_app_name = self.export_config[ConfigKeys.last_app] = \
                self._sorted_appnames[0]
        self.current_app = self.available_apps[current_app_name]

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        apps_label = Gtk.Label(label=_('_Application:'), use_underline=True)
        self._init_apps_dropdown()
        apps_label.set_mnemonic_widget(self._apps_dropdown)
        hbox.add(apps_label)
        hbox.add(self._apps_dropdown)

        # VARIANTS
        variant_label = Gtk.Label(label=_('_Variant:'), use_underline=True)
        self._init_variants_dropdown()
        variant_label.set_mnemonic_widget(self._variants_dropdown)
        hbox.add(variant_label)
        hbox.add(self._variants_dropdown)

        # HOMEPAGE
        self._homepage_button = Gtk.Button(label=_('Open _Homepage'), use_underline=True)
        self._homepage_button.connect('clicked', self._on_homepage_button)
        hbox.add(self._homepage_button)

        self.options_box.add(hbox)
        self.top_area.add(self.options_box)
        self.options_box.show_all()

        user_templates_label = Gtk.Label()
        user_templates_label.set_markup(
            _('User templates can be added to {userdir}').format(
                userdir='<a href="file://{0}">{0}</a>'.format(USER_COLORSCHEME_TEMPLATES_DIR)
            )
        )
        self.box.add(user_templates_label)
        user_templates_label.show_all()


class Plugin(OomoxExportPlugin):

    name = 'colorscheme'

    display_name = _('ColorScheme')
    description = (
        'Alacritty, Kitty'
    )
    about_text = 'Export all kinds of color schemes'
    about_links = [
        {
            'name': 'Homepage',
            'url': 'https://github.com/The-Repo-Club/oomox/tree/main/plugins/export_colorscheme',
        },
        {
            'name': 'Alacritty',
            'url': 'https://github.com/The-Repo-Club/oomox-templates/tree/main/alacritty/templates',
        },
        {
            'name': 'Kitty',
            'url': 'https://github.com/The-Repo-Club/oomox-templates/tree/main/kitty/templates',
        },
    ]
    shortcut = "<Primary>C"
    export_text = _("Export _Color Scheme…")
    export_dialog = ColorSchemeExportDialog

