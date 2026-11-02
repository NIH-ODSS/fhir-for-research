local deployment = dofile(quarto.utils.resolve_path("deployment.lua"))

function Meta(meta)
  local environment = deployment.get()
  local canonical_repository = "nih-odss/fhir-for-research"
  if environment.target == "github"
    and environment.repository:lower() == canonical_repository
    and environment.branch == environment.default_branch
    and environment.prefix == "" then
    return meta
  end

  local page = deployment.page_path():gsub("%.[^./]+$", ".html")
  local values = {
    ["local"] = environment.target == "local",
    github = environment.target == "github",
    branch = environment.branch ~= "" and environment.branch or nil,
    ["published-page"] = "https://nih-odss.github.io/fhir-for-research/" .. deployment.url_path(page)
  }
  if environment.target == "github" and environment.repository ~= "" then
    local owner = environment.repository:match("^([^/]+)/")
    if owner then
      values["compare-url"] = "https://github.com/" .. canonical_repository
        .. "/compare/main..." .. deployment.url_component(owner) .. ":"
        .. deployment.url_component(environment.branch)
    end
  end

  local file = assert(io.open(quarto.utils.resolve_path("../partials/_banner.html"), "r"))
  local template = pandoc.template.compile(file:read("*a"))
  file:close()
  local banner = pandoc.write(pandoc.Pandoc({}, values), "html", { template = template })

  -- Prepend to the navigation envelope so the banner is above the sticky header.
  local includes = meta["include-before"] or pandoc.MetaList({})
  includes:insert(1, pandoc.MetaBlocks({ pandoc.RawBlock("html", banner) }))
  meta["include-before"] = includes
  return meta
end
