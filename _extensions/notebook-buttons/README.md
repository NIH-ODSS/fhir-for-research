# Notebook buttons shortcode

On a notebook page, use the shortcode on its own line:

```markdown
{{< notebook-buttons >}}
```

The shortcode infers the notebook filename and directory from the current page.
For example, `workshops/data-analysis-cds/01-fhir-analysis.qmd` links to
`workshops/data-analysis-cds/01-fhir-analysis.ipynb`. It adds the Colab, NBViewer,
and download badges in an icon-free note callout titled "View/Run Notebook",
with introductory text and a link to Running Workshop Notebooks. The whole block
is omitted from notebook (`ipynb`) exports.

On an overview page linking to a different notebook in the same directory:

```markdown
{{< notebook-buttons notebook="01-fhir-analysis.ipynb" >}}
```

Binder is opt-in (`binder=true`) because the generated notebook branch currently
has no Binder environment specification. Other buttons can be disabled with
`colab=false`, `nbviewer=false`, or `download=false`.

## Hosting configuration

The banner and shortcode share build-time deployment metadata. GitHub Actions
and GitLab CI set these variables before Quarto renders:

| Variable | Meaning |
| --- | --- |
| `DEPLOY_TARGET` | `github`, `gitlab`, or `local` |
| `DEPLOY_URL` | Full deployed website base URL, including any preview prefix |
| `DEPLOY_REPOSITORY` | Repository owner and name |
| `DEPLOY_BRANCH` | Source branch being built |
| `DEPLOY_DEFAULT_BRANCH` | Repository's default source branch |
| `DEPLOY_PREFIX` | Directory within the published repository, empty for production or `branches/<preview-name>` for GitHub previews |

GitHub service links target `DEPLOY_REPOSITORY` on `gh-pages`, with
`DEPLOY_PREFIX` prepended to the notebook's project-relative path. This points
at the generated notebook, including for preview builds. The existing workflow
uses the last component of a source branch name for its preview directory.

On local, GitLab, and other non-GitHub builds, clicking Colab, NBViewer, or Binder
shows: “Only supported on GitHub-hosted versions of this website.” The download
button continues to link to the notebook beside the page.

The `_environment` file supplies local defaults, so `quarto preview` needs no
extra setup. Environment variables supplied by CI or the shell override those
defaults. Re-render after changing hosting settings; the banner and service
destinations are baked into the HTML.

Badge images in `images/badges/`, the workshop instructions link, and notebook
downloads use page-relative URLs. They work under arbitrary hosting prefixes.

## Overrides

`repository`, `github-ref`, `github-path`, `binder-ref`, and `binder-path` override
the inferred service destinations on GitHub builds. Path overrides are relative
to the site root; the deployment prefix is added automatically. `download-path`
overrides the download URL when the notebook is not next to the rendered page.

## Validation

Run the isolated render checks with
`UV_CACHE_DIR=.uv-cache uv run script/test-notebook-buttons.py`.
