# Baixador de Videos (yt-dlp) — uso via linha de comando
# Exemplos:
#   .\baixar.ps1 "https://youtube.com/watch?v=XXXX"           # video MP4
#   .\baixar.ps1 "https://youtube.com/watch?v=XXXX" -Audio    # audio MP3
#   .\baixar.ps1 "https://youtube.com/playlist?list=YYYY" -Playlist
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Url,

    [switch]$Audio,      # baixa apenas o audio em MP3
    [switch]$Playlist    # baixa a playlist inteira (sem isso, so o video da URL)
)

$pasta = $PSScriptRoot
$argsComuns = @()
if (-not $Playlist) { $argsComuns += "--no-playlist" }

if ($Audio) {
    $destino = if ($Playlist) { "$pasta\Audios\%(playlist_title)s\%(playlist_index)s - %(title)s.%(ext)s" }
               else           { "$pasta\Audios\%(title)s.%(ext)s" }
    yt-dlp -x --audio-format mp3 --audio-quality 0 @argsComuns -o $destino $Url
}
else {
    $destino = if ($Playlist) { "$pasta\Videos\%(playlist_title)s\%(playlist_index)s - %(title)s.%(ext)s" }
               else           { "$pasta\Videos\%(title)s.%(ext)s" }
    yt-dlp -f "bv*[vcodec^=avc1]+ba[acodec^=mp4a]/bv*+ba/b" --merge-output-format mp4 --remux-video mp4 @argsComuns -o $destino $Url
}
