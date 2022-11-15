from mqtt_as import config

# WiFi configuration
config['ssid'] = 'your_network_name'
config['wifi_pw'] = 'your_password'

# MQTT broker configuration
config['server'] = '192.168.0.10'
config['topic'] = 'blinkenxmas'

# Configuration of the WS2812 strip
config['led_count'] = 50
config['fps'] = 60
