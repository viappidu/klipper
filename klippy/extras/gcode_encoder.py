# Support for executing gcode when a hardware button is pressed or released.
#
# Copyright (C) 2019 Alec Plumb <alec@etherwalker.com>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import logging, time

LONG_CLICK_DURATION = 1.500
DOUBLE_CLICK_THRESHOLD = 0.400

class GCodeEncoder:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.timer = 0
        buttons = self.printer.load_object(config, "buttons")
        # Register rotary encoder
        encoder_pins = config.get('encoder_pins', None)
        encoder_steps_per_detent = config.getchoice('encoder_steps_per_detent',
                                                    {2: 2, 4: 4}, 4)
        if encoder_pins is not None:
            try:
                pin1, pin2 = encoder_pins.split(',')
            except:
                raise config.error("Unable to parse encoder_pins")
            buttons.register_rotary_encoder(pin1.strip(), pin2.strip(),
                                            self.encoder_cw_callback,
                                            self.encoder_ccw_callback,
                                            encoder_steps_per_detent)
        self.encoder_fast_rate = config.getfloat('encoder_fast_rate',
                                                 .030, above=0.)
        self.last_encoder_cw_eventtime = 0
        self.last_encoder_ccw_eventtime = 0
        self.input_min = config.getfloat('input_min', None)
        self.input_max = config.getfloat('input_max', 1.0)
        self.input_min = config.getfloat('input_step',
                                        .01, above=0.)
        # Register click button
        # self.current_state = "IDLE"
        # self.last_click_time = None
        self.is_short_click = False
        self.click_timer = self.reactor.register_timer(self.long_click_event)
        self.register_button(config, 'click_pin', self.click_callback)
        # scripts
        self.gcode_queue = []
        self._scripts = {}
        gcode_macro = self.printer.load_object(config, 'gcode_macro')
        self._scripts['click'] = gcode_macro.load_template(config, 'click_gcode', '')
        self._scripts['double_click'] = gcode_macro.load_template(config, 'double_click_gcode', '')
        self._scripts['long_click'] = gcode_macro.load_template(config, 'long_click_gcode', '')
        self._scripts['release_template'] = gcode_macro.load_template(config,
                                                          'release_gcode', '')
        self._scripts['up'] = gcode_macro.load_template(config, 'up_gcode', '')
        self._scripts['fast_up'] = gcode_macro.load_template(config, 'fast_up_gcode', '')
        self._scripts['down'] = gcode_macro.load_template(config, 'down_gcode', '')
        self._scripts['fast_down'] = gcode_macro.load_template(config, 'fast_down_gcode', '')
        self.gcode = self.printer.lookup_object('gcode')

    def register_button(self, config, name, callback):
        pin = config.get(name, None)
        if pin is None:
            return
        buttons = self.printer.lookup_object("buttons")
        buttons.register_buttons([pin], callback)

    # Rotary encoder callbacks
    def encoder_cw_callback(self, eventtime):
        fast_rate = ((eventtime - self.last_encoder_cw_eventtime)
                     <= self.encoder_fast_rate)
        self.last_encoder_cw_eventtime = eventtime
        if fast_rate:
            self.key_event('fast_up', eventtime)
        else:
            self.key_event('up', eventtime)

    def encoder_ccw_callback(self, eventtime):
        fast_rate = ((eventtime - self.last_encoder_ccw_eventtime)
                     <= self.encoder_fast_rate)
        self.last_encoder_ccw_eventtime = eventtime
        if fast_rate:
            self.key_event('fast_down', eventtime)
        else:
            self.key_event('down', eventtime)
 
    def long_click_event(self, eventtime):
        self.is_short_click = False
        # self.callback('long_click', eventtime)
        self.key_event('long_click', eventtime)
        return self.reactor.NEVER

    def click_callback(self, eventtime, state):
        if state:
            self.is_short_click = True
            self.reactor.update_timer(self.click_timer, eventtime + LONG_CLICK_DURATION)
        elif self.is_short_click:
            self.reactor.update_timer(self.click_timer, self.reactor.NEVER)
            self.key_event('click', eventtime)


        # if state == "IDLE":
        #     state = "BUTTON_DOWN"
        #     last_click_time = time.time()
        # elif state == "BUTTON_UP":
        #     duration = time.time() - last_click_time
        #     if duration >= LONG_CLICK_DURATION:
        #         state = "LONG_CLICK"
        #         self.key_event('long_click', eventtime)
        #     else:
        #         if last_click_time is not None and time.time() - last_click_time <= DOUBLE_CLICK_THRESHOLD:
        #             state = "DOUBLE_CLICK"
        #             last_click_time = None
        #             self.key_event('double_click', eventtime)
        #         else:
        #             last_click_time = time.time()
        #             self.key_event('click', eventtime)
        # else:
        #     last_click_time = time.time()

        # if state:
        #     if self.current_state == "IDLE":
        #         self.current_state = "BUTTON_DOWN"
        #         self.last_click_time = time.time()
        #     elif self.current_state == "BUTTON_UP":
        #         duration = time.time() - self.last_click_time
        #         if duration >= LONG_CLICK_DURATION:
        #             state = "LONG_CLICK"
        #             self.key_event('long_click', eventtime)
        #         else:
        #             if self.last_click_time is not None and time.time() - self.last_click_time <= DOUBLE_CLICK_THRESHOLD:
        #                 state = "DOUBLE_CLICK"
        #                 self.last_click_time = None
        #                 self.key_event('double_click', eventtime)
        #             else:
        #                 self.last_click_time = time.time()
        #                 self.key_event('click', eventtime)
        # else:
        #     self.last_click_time = time.time()
            
        # if self.current_state == "BUTTON_DOWN":
        #     self.current_state = "BUTTON_UP"
        # elif self.current_state == "LONG_CLICK":
        #     self.current_state = "IDLE"
        # else:
        #     pass # Ignore other button releases

    # Other button callbacks
    def key_event(self, key, eventtime):
        if key == 'click':
            self.queue_gcode(self._scripts[key])
        if key == 'double_click':
            self.queue_gcode(self._scripts[key])
        elif key == 'long_click':
            self.queue_gcode(self._scripts[key])
        elif key == 'up':
            self.queue_gcode(self._scripts[key])
        elif key == 'fast_up':
            self.queue_gcode(self._scripts[key])
        elif key == 'down':
            self.queue_gcode(self._scripts[key])
        elif key == 'fast_down':
            self.queue_gcode(self._scripts[key])

    def queue_gcode(self, script):
        if not script:
            return
        if not self.gcode_queue:
            reactor = self.printer.get_reactor()
            reactor.register_callback(self.dispatch_gcode)
        self.gcode_queue.append(script)

    def dispatch_gcode(self, eventtime):
        while self.gcode_queue:
            script = self.gcode_queue[0]
            try:
                self.gcode.run_script(script.render())
            except Exception:
                logging.exception("Script running error")
            self.gcode_queue.pop(0)

def load_config_prefix(config):
    return GCodeEncoder(config)
