local deployment = {}

local function env(name, default)
  local value = os.getenv(name)
  if value == nil or value == "" then
    return default
  end
  return value
end

function deployment.get()
  return {
    target = env("DEPLOY_TARGET", "local"),
    url = env("DEPLOY_URL", "http://localhost:1414"):gsub("/+$", ""),
    repository = env("DEPLOY_REPOSITORY", ""),
    branch = env("DEPLOY_BRANCH", ""),
    default_branch = env("DEPLOY_DEFAULT_BRANCH", "main"),
    prefix = env("DEPLOY_PREFIX", ""):gsub("^/+", ""):gsub("/+$", ""),
  }
end

function deployment.page_path()
  local path = quarto.doc.input_file
  if quarto.project.directory then
    path = pandoc.path.make_relative(path, quarto.project.directory)
  end
  return path:gsub("^%./", "")
end

function deployment.project_path(path)
  return (quarto.project.offset or ".") .. "/" .. path
end

function deployment.url_component(value)
  return (value:gsub("([^%w%-._~])", function(character)
    return string.format("%%%02X", string.byte(character))
  end))
end

function deployment.url_path(value)
  return (value:gsub("[^/]+", deployment.url_component))
end

return deployment
