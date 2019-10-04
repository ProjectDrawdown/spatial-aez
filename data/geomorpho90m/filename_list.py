import glob
import tarfile


files = []
for tgzname in glob.glob('*.tar.gz'):
    tar = tarfile.open(tgzname)
    for member in tar.getnames():
        print(f"/vsitar/{tgzname}/{member}")
