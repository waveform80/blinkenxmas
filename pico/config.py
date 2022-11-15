from mqtt_as import config

# WiFi configuration
config['ssid'] = 'your-ssid-here'
config['wifi_pw'] = 'your-ssid-password'

# MQTT broker configuration
config['server'] = 'broker'
config['topic'] = 'blinkenxmas'

# Configuration of the WS2812 strip
config['led_count'] = 50
config['fps'] = 60
