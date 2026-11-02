```{=html}
<ul class="roles-select-list">
<% for (const item of items) { %>
  <li>
    <label for="chk_<%- item.value %>" class="btn-role">
      <input
        type="radio"
        name="role-select"
        data-role="<%- item.value %>"
        id="chk_<%- item.value %>">
      <%- item.name %>
    </label>
  </li>
<% } %>
</ul> 
```
