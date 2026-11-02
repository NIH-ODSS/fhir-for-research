function Meta(meta)
  local input_file = (quarto.doc.input_file or ""):gsub("\\", "/")

  local section_dirs = { "/modules/", "/webinars/", "/workshops/" }

  meta.in_modules = false
  for _, dir in ipairs(section_dirs) do
    local found = input_file:find(dir, 1, true)
    if found then
      meta.in_modules = true
      break
    end
  end

  return meta
end
