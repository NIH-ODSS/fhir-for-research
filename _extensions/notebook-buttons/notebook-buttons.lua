local deployment = dofile(quarto.utils.resolve_path("../../lua/deployment.lua"))

local function stringify(value)
  if value == nil then
    return nil
  end

  return pandoc.utils.stringify(value)
end

local function option(kwargs, name, default)
  local value = stringify(kwargs[name])
  if value == nil or value == "" then
    return default
  end

  return value
end

local function enabled(kwargs, name, default)
  return option(kwargs, name, default or "true"):lower() ~= "false"
end

local function badge_path(filename)
  return deployment.project_path("images/badges/" .. filename)
end

local function escape_html(value)
  return value
    :gsub("&", "&amp;")
    :gsub('"', "&quot;")
    :gsub("<", "&lt;")
    :gsub(">", "&gt;")
end

local function badge(href, image, alt, download)
  if href == nil then
    return string.format(
      '<button type="button" class="border-0 bg-transparent p-0" onclick="alert(\'Only supported on GitHub-hosted versions of this website.\')"><img src="%s" alt="%s"></button>',
      escape_html(image),
      escape_html(alt)
    )
  end

  local download_attribute = download and " download" or ""

  return string.format(
    '<a href="%s"%s><img src="%s" alt="%s"></a>',
    escape_html(href),
    download_attribute,
    escape_html(image),
    escape_html(alt)
  )
end

return {
  ["notebook-buttons"] = function(args, kwargs)
    if quarto.doc.is_format("ipynb") then
      return pandoc.Blocks({})
    end

    local hosting = deployment.get()
    local page = deployment.page_path()
    local stem = pandoc.path.split_extension(pandoc.path.filename(page))
    local notebook = option(kwargs, "notebook", stringify(args[1]) or stem .. ".ipynb")
    local repository = option(kwargs, "repository", hosting.repository)
    local on_github = hosting.target == "github"
    if on_github and repository == "" then
      error("GitHub notebook buttons require DEPLOY_REPOSITORY or repository=...")
    end

    local notebook_path = pandoc.path.normalize(pandoc.path.join({pandoc.path.directory(page), notebook}))
    local github_path = option(kwargs, "github-path", notebook_path)
    local binder_path = option(kwargs, "binder-path", github_path)
    local download_path = option(kwargs, "download-path", "./" .. deployment.url_path(notebook))
    local github_ref = option(kwargs, "github-ref", "gh-pages")
    local binder_ref = option(kwargs, "binder-ref", github_ref)
    if hosting.prefix ~= "" then
      github_path = hosting.prefix .. "/" .. github_path
      binder_path = hosting.prefix .. "/" .. binder_path
    end
    local github_location = deployment.url_path(repository) .. "/blob/"
      .. deployment.url_component(github_ref) .. "/" .. deployment.url_path(github_path)
    local buttons = {}

    if enabled(kwargs, "colab") then
      table.insert(buttons, badge(
        on_github and "https://colab.research.google.com/github/" .. github_location or nil,
        badge_path("colab.svg"),
        "Open in Colab"
      ))
    end

    if enabled(kwargs, "nbviewer") then
      local notebook_url = download_path
      if not notebook_url:match("^https?://") then
        local path = pandoc.path.normalize(pandoc.path.join({pandoc.path.directory(page), download_path}))
        notebook_url = hosting.url .. "/" .. path:gsub("^%./", "")
      end
      table.insert(buttons, badge(
        on_github and "https://nbviewer.org/urls/" .. notebook_url:gsub("^https?://", "") or nil,
        badge_path("nbviewer.svg"),
        "View in NBViewer"
      ))
    end

    if enabled(kwargs, "download") then
      table.insert(buttons, badge(
        download_path,
        badge_path("download_notebook.svg"),
        "Download notebook",
        true
      ))
    end

    if enabled(kwargs, "binder", "false") then
      table.insert(buttons, badge(
        on_github and "https://mybinder.org/v2/gh/" .. deployment.url_path(repository) .. "/"
          .. deployment.url_component(binder_ref) .. "?urlpath="
          .. deployment.url_component("/doc/tree/" .. binder_path) or nil,
        badge_path("binder.svg"),
        "Launch Binder"
      ))
    end

    return pandoc.Div({
      quarto.Callout({
        type = "note",
        title = "View/Run Notebook",
        icon = false,
        content = pandoc.Blocks({
          pandoc.Para({pandoc.Str("This page can be viewed or run as a Jupyter notebook:")}),
          pandoc.Para({pandoc.RawInline("html", table.concat(buttons, " "))}),
          pandoc.Para({
            pandoc.Str("See"),
            pandoc.Space(),
            pandoc.Link("Running Workshop Notebooks", deployment.project_path("workshops/running-notebooks.html")),
            pandoc.Space(),
            pandoc.Str("for more information about these options."),
          }),
        }),
      }),
    }, pandoc.Attr("", {"content-hidden"}, {["when-format"] = "ipynb"}))
  end
}
