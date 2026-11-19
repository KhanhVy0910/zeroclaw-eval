with open('config/config.toml', 'r', encoding='utf-8') as f:
    for line in f:
        stripped = line.strip()
        if stripped.startswith('api_key') or 'enc2:' in line:
            print('api_key = "<REDACTED_SECRET>"')
        else:
            print(line, end='')
