local deployment = dofile(quarto.utils.resolve_path("deployment.lua"))

function CodeBlock(block)
  block.text = block.text:gsub("{{DEPLOY_URL}}", function()
    return deployment.get().url
  end)
  return block
end
