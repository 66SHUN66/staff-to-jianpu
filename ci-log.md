# 构建失败日志

```
Traceback (most recent call last):
  File "D:\a\staff-to-jianpu\staff-to-jianpu\scripts\build.py", line 21, in main
    from lilipu.icon import ensure_icon
ModuleNotFoundError: No module named 'lilipu'

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "D:\a\staff-to-jianpu\staff-to-jianpu\scripts\build.py", line 46, in <module>
    raise SystemExit(main())
                     ^^^^^^
  File "D:\a\staff-to-jianpu\staff-to-jianpu\scripts\build.py", line 24, in main
    print(f"[warn] \u56fe\u6807\u751f\u6210\u5931\u8d25\uff0c\u7ee7\u7eed\u6253\u5305: {exc}")
  File "C:\hostedtoolcache\windows\Python\3.11.9\x64\Lib\encodings\cp1252.py", line 19, in encode
    return codecs.charmap_encode(input,self.errors,encoding_table)[0]
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
UnicodeEncodeError: 'charmap' codec can't encode characters in position 7-17: character maps to <undefined>
```
