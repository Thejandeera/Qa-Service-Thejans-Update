import glob

dockerfiles = glob.glob('Dockerfile.*')
for df in dockerfiles:
    with open(df, 'r') as f:
        content = f.read()
    content = content.replace('COPY src/ src/', 'COPY src/ src/\nCOPY resources/ resources/')
    with open(df, 'w') as f:
        f.write(content)

