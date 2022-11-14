from mqtt_as import config

config['server'] = '192.168.0.10'  # Change to suit

# Not needed if you're only using ESP8266
config['ssid'] = 'your_network_name'
config['wifi_pw'] = 'your_password'

# Configuration of the WS2812 strip
config['led_count'] = 50
config['fps'] = 60
