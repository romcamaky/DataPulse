{% test unique_combination_of_columns(model, combination_of_columns) %}
  {# Fails when any (combination_of_columns) group appears more than once. #}
  select {{ combination_of_columns[0] }}
  from {{ model }}
  group by
    {% for col in combination_of_columns -%}
      {{ col }}{% if not loop.last %}, {% endif %}
    {%- endfor %}
  having count(*) > 1
{% endtest %}
