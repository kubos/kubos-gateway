class Command(object):
    def __init__(self, json_command):
        self.json_command = json_command
        self.type = json_command["type"]
        self.id = json_command["id"]
        self.path = json_command["path"]
        self.subsystem = self.path.split('.')[-1]
        self.fields = {
            field["name"]: field["value"] for field in json_command["fields"]}
