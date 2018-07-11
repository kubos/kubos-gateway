class CommandResult:
    def __init__(self, command, error=None):
        self.command = command
        self.sent = False
        self.errors = []
        if error:
            self.errors.append(error)
        self.payload = None

    def validate_range(self, field, start, end, field_type, error):
        if not self.command.fields[field]:
            self.errors.append(f"{field} is required")
        elif not isinstance(self.command.fields[field], field_type):
            self.errors.append(f"{field} must be a {field_type}")
        elif self.command.fields[field] < start or self.command.fields[field] >= end:
            self.errors.append(error)

    def validate_presence(self, field, error):
        if not self.command.fields[field] or not isinstance(self.command.fields[field], str) or len(
                self.command.fields[field]) == 0:
            self.errors.append(error)

    def valid(self):
        return len(self.errors) == 0