INDEX_SETTINGS = {}

INDEX_SETTINGS['es'] = {
  'settings': {
    'analysis': {
      'filter': {
        'spanish_stemmer': {
          'type': 'stemmer',
          'language': 'light_spanish'
        },
      },
      'analyzer': {
        'custom_spanish': {
          'type':'custom',
          'tokenizer': 'standard',
          'filter': [
            'spanish_stemmer',
            'lowercase',
          ],
        },
      },
    },
  },
  'mappings': {
    'dynamic': 'strict',
    'properties': {
      'text': {
        'type': 'text',
        'analyzer': 'custom_spanish',
        'index_options': 'offsets',
      },
      'info': {
        'type': 'object',
        'enabled': False,
      },
    },
  },
}
