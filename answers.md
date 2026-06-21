yt_dlp/downloader/bunnycdn.py / BunnyCdnFD - 2 metody
..\repos\yt-dlp\yt_dlp\downloader\bunnycdn.py
    C 11:0 BunnyCdnFD - A (3)
    M 32:4 BunnyCdnFD.ping_thread - A (3)
    M 18:4 BunnyCdnFD.real_download - A (1)

Dziedziczy po FileDownloader -> object
importuje 7 modułów 

yt_dlp/downloader/http.py / HttpFD - 1 metoda
..\repos\yt-dlp\yt_dlp\downloader\http.py
    C 23:0 HttpFD - C (13)
    M 24:4 HttpFD.real_download - C (12)

Dziedziczy po FileDownloader -> object
importuje 15 modułów 


yt_dlp/downloader/fragment.py / FragmentFD - 17 metod (+1 metoda od HttpQuietDownloader)
..\repos\yt-dlp\yt_dlp\downloader\fragment.py
    M 157:4 FragmentFD._prepare_frag_download - C (15)
    M 431:4 FragmentFD.download_and_append_fragments - C (13)
    M 367:4 FragmentFD.download_and_append_fragments_multiple - B (10)
    M 285:4 FragmentFD._finish_frag_download - B (8)
    C 26:0 FragmentFD - A (5)
    M 111:4 FragmentFD._download_fragment - A (5)
    M 82:4 FragmentFD._read_ytdl_file - A (4)
    M 132:4 FragmentFD._read_fragment - A (4)
    M 321:4 FragmentFD._prepare_external_frag_download - A (4)
    M 79:4 FragmentFD.__do_ytdl_file - A (3)
    M 95:4 FragmentFD._write_ytdl_file - A (3)
    M 146:4 FragmentFD._append_fragment - A (3)
    C 19:0 HttpQuietDownloader - A (2)
    M 67:4 FragmentFD.report_skip_fragment - A (2)
    M 71:4 FragmentFD._prepare_url - A (2)
    M 20:4 HttpQuietDownloader.to_screen - A (1)
    M 62:4 FragmentFD.report_retry_fragment - A (1)
    M 75:4 FragmentFD._prepare_and_start_frag_download - A (1)
    M 225:4 FragmentFD._start_frag_download - A (1)
    M 341:4 FragmentFD.decrypter - A (1)

Dziedziczy po HttpFD -> FileDownloader -> object
importuje 19 modułów 

Najgorzej wypada FragmentFD.