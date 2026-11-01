from datetime import datetime
from core.settings import data_dir, read_json, write_json


class History:
    def __init__(self, root=None):
        self.path = (root or data_dir()) / 'history.json'
        self.entries = read_json(self.path, [])
        if not isinstance(self.entries, list):
            raise RuntimeError('Неверный формат history.json')

    def add(self, entry):
        entry['time'] = datetime.now().astimezone().isoformat(timespec='seconds')
        self.entries.insert(0, entry)
        self.entries = self.entries[:500]
        write_json(self.path, self.entries)
