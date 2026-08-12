# NCRMove statistical analysis: traffic and weather effects on cancellations.
# Run from the repository root with:
#   Rscript r/traffic_weather_cancellation_analysis.R

suppressPackageStartupMessages(library(data.table))

project_root <- normalizePath(getwd())
raw_data <- file.path(project_root, "data", "raw")
cleaned_trips <- file.path(project_root, "outputs", "cleaning", "trips_cleaned.csv")
output_dir <- file.path(project_root, "outputs", "r_analysis")
dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

if (!file.exists(cleaned_trips)) {
  stop("Cleaned trips are missing. Run python3 python/data_cleaning/clean_trips.py first.")
}

# Read only the trip fields required for this statistical study.
trips <- fread(
  cleaned_trips,
  select = c("trip_id", "request_timestamp", "pickup_zone_id", "wait_time_min", "status")
)
traffic <- fread(file.path(raw_data, "traffic.csv"))
weather <- fread(file.path(raw_data, "weather.csv"))

trips[, cancelled := as.integer(status == "Cancelled")]
setkey(traffic, zone_id, timestamp)
setkey(weather, timestamp)

# The synthetic extracts use matching hourly timestamps; keyed joins avoid a
# large Cartesian merge while preserving the trip-level analytical population.
trips[traffic, on = .(pickup_zone_id = zone_id, request_timestamp = timestamp),
      `:=`(congestion_level = i.congestion_level,
           avg_speed_kmph = i.avg_speed_kmph,
           traffic_index = i.traffic_index)]
trips[weather, on = .(request_timestamp = timestamp),
      `:=`(rainfall_mm = i.rainfall_mm,
           visibility_km = i.visibility_km,
           weather_condition = i.weather_condition)]

analysis_data <- trips[complete.cases(
  traffic_index, rainfall_mm, visibility_km, weather_condition, wait_time_min
)]
if (!nrow(analysis_data)) stop("No trip records matched traffic and weather data.")

traffic_summary <- analysis_data[, .(
  trips = .N,
  cancellation_rate = mean(cancelled),
  avg_wait_time_min = mean(wait_time_min),
  avg_traffic_index = mean(traffic_index)
), by = congestion_level][order(match(congestion_level, c("Low", "Medium", "High", "Severe")))]

weather_summary <- analysis_data[, .(
  trips = .N,
  cancellation_rate = mean(cancelled),
  avg_wait_time_min = mean(wait_time_min),
  avg_rainfall_mm = mean(rainfall_mm)
), by = weather_condition][order(-cancellation_rate)]

fwrite(traffic_summary, file.path(output_dir, "cancellation_by_congestion.csv"))
fwrite(weather_summary, file.path(output_dir, "cancellation_by_weather.csv"))

# A reproducible sample keeps the logistic-regression fit quick on a laptop
# while retaining a large, representative analytical population.
set.seed(20260812)
sample_size <- min(150000L, nrow(analysis_data))
model_data <- analysis_data[sample.int(.N, sample_size)]
model <- glm(
  cancelled ~ traffic_index + rainfall_mm + visibility_km + factor(weather_condition),
  data = model_data,
  family = binomial()
)

model_coefficients <- as.data.table(summary(model)$coefficients, keep.rownames = "term")
setnames(
  model_coefficients,
  c("Estimate", "Std. Error", "z value", "Pr(>|z|)"),
  c("estimate", "std_error", "z_value", "p_value")
)
model_coefficients[, odds_ratio := exp(estimate)]
fwrite(model_coefficients, file.path(output_dir, "cancellation_logistic_regression.csv"))

png(file.path(output_dir, "traffic_weather_cancellation.png"), width = 1600, height = 700, res = 160)
par(mfrow = c(1, 2), mar = c(5, 5, 4, 1))
barplot(
  traffic_summary$cancellation_rate * 100,
  names.arg = traffic_summary$congestion_level,
  col = c("#6BAED6", "#3182BD", "#08519C", "#08306B"),
  ylab = "Cancellation rate (%)", main = "Cancellations by traffic congestion"
)
barplot(
  weather_summary$cancellation_rate * 100,
  names.arg = weather_summary$weather_condition,
  col = "#D97706", las = 2,
  ylab = "Cancellation rate (%)", main = "Cancellations by weather condition"
)
dev.off()

traffic_peak <- traffic_summary[which.max(cancellation_rate)]
weather_peak <- weather_summary[which.max(cancellation_rate)]
traffic_low <- traffic_summary[which.min(cancellation_rate)]
traffic_difference_pp <- (traffic_peak$cancellation_rate - traffic_low$cancellation_rate) * 100
traffic_term <- model_coefficients[term == "traffic_index"]

report <- sprintf(
  paste(
    "# NCRMove Traffic & Weather Statistical Analysis",
    "",
    "This analysis uses **%s** cleaned synthetic trips with matched zone-hour traffic and hourly weather data.",
    "",
    "## Method",
    "",
    "A descriptive comparison reports cancellation and wait metrics by congestion and weather condition. A logistic regression on a reproducible random sample of **%s** trips estimates the association between cancellation probability and traffic index, rainfall, visibility, and weather condition. These associations are not causal claims.",
    "",
    "## Headline findings",
    "",
    "* **Highest cancellation by congestion:** %s at **%.2f%%**.",
    "* **Lowest cancellation by congestion:** %s at **%.2f%%** — a difference of **%.2f percentage points**.",
    "* **Highest cancellation by weather:** %s at **%.2f%%**.",
    "* **Traffic-index odds ratio:** **%.4f** per one-point increase (logistic regression p-value: **%.3g**).",
    "",
    "## Outputs",
    "",
    "* `cancellation_by_congestion.csv` — operational cancellation and wait metrics by traffic band.",
    "* `cancellation_by_weather.csv` — operational cancellation and wait metrics by weather condition.",
    "* `cancellation_logistic_regression.csv` — model coefficients, p-values, and odds ratios.",
    "* `traffic_weather_cancellation.png` — dashboard-ready comparison chart.",
    "",
    "The NCRMove data is synthetic and these results must not be represented as measured real-world NCR ride-hailing behaviour.",
    sep = "\n"
  ),
  format(nrow(analysis_data), big.mark = ","),
  format(sample_size, big.mark = ","),
  traffic_peak$congestion_level, traffic_peak$cancellation_rate * 100,
  traffic_low$congestion_level, traffic_low$cancellation_rate * 100,
  traffic_difference_pp,
  weather_peak$weather_condition, weather_peak$cancellation_rate * 100,
  traffic_term$odds_ratio, traffic_term$p_value
)
writeLines(report, file.path(output_dir, "traffic_weather_findings.md"))

cat(sprintf("R analysis complete. Outputs: %s\n", output_dir))
