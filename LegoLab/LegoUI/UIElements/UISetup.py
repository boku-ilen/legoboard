from typing import Tuple, Callable, List
from functools import partial
import numpy as np

from .UIElement import UIElement, UIActionType
from .Button import Button
from .UIStructureBlock import UIStructureBlock
from .MiniMap import MiniMap
from .ProgressBar import ProgressBar
from ..MainMap import MainMap
from ..MapActions import MapActions
from ...ConfigManager import ConfigManager
from ...ServerCommunication import ServerCommunication


def setup_ui(main_map: MainMap, config: ConfigManager, server: ServerCommunication) \
        -> Tuple[UIElement, MiniMap, Callable]:
    action_map = main_map.action_map

    # get config settings
    scale_factor = config.get("ui-settings", "scale-factor")
    button_size = np.asarray((50 * scale_factor, 50 * scale_factor))

    # define constants
    screen_width = config.get("beamer-resolution", "width")
    screen_height = config.get("beamer-resolution", "height")
    bot_right_corner = np.asarray([screen_width, screen_height])
    nav_toggle_pos = np.asarray([20 * scale_factor, 20 * scale_factor])
    nav_block_pos = np.asarray([-10 * scale_factor, -10 * scale_factor])
    nav_block_size = np.asarray([300 * scale_factor, 600 * scale_factor])
    x_offset = np.multiply(button_size, np.asarray([1, 0]))
    y_offset = np.multiply(button_size, np.asarray([0, 1]))
    cross_offset = x_offset * 0.5 + y_offset * 1.5  # default button offset for the pan controls
    pan_offset = cross_offset + x_offset * 4  # default button offset for the zoom controls

    # create root element
    root = UIElement()

    # create other elements
    toggle_nav_block_button = Button(config, nav_toggle_pos, button_size, 'toggle navigation block')
    navigation_block = UIStructureBlock(config, nav_block_pos, nav_block_size)
    pan_up_button = Button(config, cross_offset + x_offset, button_size, 'pan up', 'button_up')
    pan_down_button = Button(config, cross_offset + x_offset + y_offset * 2, button_size, 'pan down', 'button_down')
    pan_left_button = Button(config, cross_offset + y_offset, button_size, 'pan left', 'button_left')
    pan_right_button = Button(config, cross_offset + y_offset + x_offset * 2, button_size, 'pan right', 'button_right')
    zoom_in_button = Button(config, pan_offset, button_size, 'zoom in', 'button_zoom_in')
    zoom_out_button = Button(config, pan_offset + y_offset * 2, button_size, 'zoom out', 'button_zoom_out')
    mini_map = MiniMap(
        config,
        'mini_map',
        np.asarray([10 * scale_factor, 300 * scale_factor]),
        np.asarray([280 * scale_factor, 280 * scale_factor]),
        main_map
    )
    progress_bar_wind = ProgressBar(
        config,
        bot_right_corner - x_offset - y_offset * 5,
        x_offset / 2 + y_offset * 4.5,
        False,
        True,
        [(255, 0, 0)]       # bgr
    )
    progress_bar_pv = ProgressBar(
        config,
        bot_right_corner - x_offset * 2 - y_offset * 5,
        x_offset / 2 + y_offset * 4.5,
        False,
        True,
        [(0, 0, 255)]       # bgr
    )

    asset_type_id = config.get("server", "wind_id")
    progress_bar_wind.target = server.get_energy_target(asset_type_id)
    progress_bar_wind.progress_calculation = partial(server.get_energy_contrib, asset_type_id)

    asset_type_id = config.get("server", "pv_id")
    progress_bar_pv.target = server.get_energy_target(asset_type_id)
    progress_bar_pv.progress_calculation = partial(server.get_energy_contrib, asset_type_id)

    # setup hierarchy
    root.add_child(toggle_nav_block_button)
    toggle_nav_block_button.add_child(navigation_block)
    navigation_block.add_child(pan_up_button)
    navigation_block.add_child(pan_down_button)
    navigation_block.add_child(pan_left_button)
    navigation_block.add_child(pan_right_button)
    navigation_block.add_child(zoom_in_button)
    navigation_block.add_child(zoom_out_button)
    navigation_block.add_child(mini_map)
    root.add_child(progress_bar_wind)
    root.add_child(progress_bar_pv)

    # set nav block invisible
    navigation_block.set_visible(False)

    # set button functionality
    pan_up_button.set_callback(UIActionType.PRESS, action_map[MapActions.PAN_UP])
    pan_down_button.set_callback(UIActionType.PRESS, action_map[MapActions.PAN_DOWN])
    pan_left_button.set_callback(UIActionType.PRESS, action_map[MapActions.PAN_LEFT])
    pan_right_button.set_callback(UIActionType.PRESS, action_map[MapActions.PAN_RIGHT])
    zoom_in_button.set_callback(UIActionType.PRESS, action_map[MapActions.ZOOM_IN])
    zoom_out_button.set_callback(UIActionType.PRESS, action_map[MapActions.ZOOM_OUT])

    if config.get("ui-settings", "nav-block-toggle"):
        # this makes the button toggle
        toggle_nav_block_button.set_callback(
            UIActionType.PRESS,
            lambda brick: navigation_block.set_visible(not navigation_block.visible)
        )
    else:
        # this shows the nav_block only when a brick is on the button
        toggle_nav_block_button.set_callback(UIActionType.PRESS, lambda brick: navigation_block.set_visible(True))
        toggle_nav_block_button.set_callback(UIActionType.RELEASE, lambda brick: navigation_block.set_visible(False))

    return root, mini_map, partial(update_progress_bars, [progress_bar_wind, progress_bar_pv])


# calls the update function on all progress bars that were passed in
def update_progress_bars(progress_bars: List[ProgressBar]):
    for bar in progress_bars:
        bar.calculate_progress()
