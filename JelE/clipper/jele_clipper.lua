-- JelE Clipper: starts the clipper automatically when OBS starts.
-- Add it: Tools -> Scripts -> + -> pick this file (C:\JelE\clipper\jele_clipper.lua).
obs = obslua

function script_description()
  return "<b>JelE Clipper</b><br>Starts the clipper in the background when OBS starts.<br>Set the dock to <i>file:///C:/JelE/clipper/dock.html</i>."
end

function script_load(settings)
  local dir = script_path():gsub("/", "\\")
  local bat = dir .. "start.bat"
  -- minimised window; if the clipper already runs, the second copy closes itself
  os.execute('start "JelE Clipper" /min cmd /c ""' .. bat .. '" --no-browser"')
end
