# -*- mode: python ; coding: utf-8 -*-

block_cipher = None


a = Analysis(['sender.py'],
             pathex=['C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python36\\Lib\\site-packages', 'D:\\blinqr-master'],
             binaries=[('C:\\Users\\Administrator\\AppData\\Local\Programs\\Python\\Python36\\Lib\\site-packages\\pyzbar\\libiconv.dll','.'),('C:\\Users\\Administrator\\AppData\\Local\Programs\\Python\\Python36\\Lib\\site-packages\\pyzbar\\libzbar-64.dll','.')],
             datas=[],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='sender',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=True )
