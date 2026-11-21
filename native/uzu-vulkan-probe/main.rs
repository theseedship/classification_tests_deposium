//! Explicit context probe, or a separately requested local synthetic decision fixture.
use std::path::PathBuf;
use ash::vk;
use serde_json::{json, Value};
use uzu_engine::{
    backends::{Backend, BackendSelection, select_backend, vulkan::{VkPhysicalDevice, Vulkan}},
    engine::{Engine, decision_model::DecisionModelError},
};

struct DecisionProbe {
    path: PathBuf,
    backend: String,
}

impl BackendSelection for DecisionProbe {
    type Output = (Value, i32);
    type Error = &'static str;

    async fn select<B: Backend>(self) -> Result<Self::Output, Self::Error> {
        eprintln!("probe_stage=decision_context backend={}", B::NAME);
        if B::NAME != self.backend {
            return Err("requested_backend_mismatch");
        }
        let mut result = json!({"schema_version": "deposium.uzu-vulkan-decision-probe/v1",
            "status": "error", "scope": "caller_supplied_synthetic_fixture_only_no_campaign",
            "requested_backend": B::NAME, "actual_backend": "not_observed", "model_loaded": false, "inference_run": false,
            "native_context_created": false, "campaign_cases": 0});
        let engine = match Engine::<B>::new().await {
            Ok(engine) => engine,
            Err(_) => {
                result["error_code"] = json!("decision_context_creation_failed");
                return Ok((result, 2));
            }
        };
        result["native_context_created"] = json!(true);
        result["actual_backend"] = json!(B::NAME);
        eprintln!("probe_stage=decision_model_load");
        let model = match engine.load_decision_model(&self.path).await {
            Ok(model) => model,
            Err(_) => {
                result["error_code"] = json!("local_decision_model_load_failed");
                return Ok((result, 2));
            }
        };
        result["model_loaded"] = json!(true);
        eprintln!("probe_stage=decision_model_loaded");
        let codes = model.decision_config().codes.len();
        if codes < 2 {
            result["error_code"] = json!("fixture_needs_two_codes");
            return Ok((result, 2));
        }
        let controls = json!({
            "empty_input_rejected": matches!(model.probabilities(&[], 2).await, Err(DecisionModelError::EmptyInput)),
            "zero_options_rejected": matches!(model.probabilities(&[0], 0).await,
                Err(DecisionModelError::InvalidOptionCount { .. })),
            "excess_options_rejected": matches!(model.probabilities(&[0], codes + 1).await,
                Err(DecisionModelError::InvalidOptionCount { .. }))});
        let controls_valid = controls.as_object().is_some_and(|rows| rows.values().all(|value| value == true));
        result["controls"] = controls;
        eprintln!("probe_stage=negative_controls_collected");
        if !controls_valid {
            result["error_code"] = json!("decision_negative_control_not_rejected");
            return Ok((result, 2));
        }
        let mut responses = Vec::new();
        for tokens in [vec![0], vec![1], vec![0, 1], vec![1, 0]] {
            eprintln!("probe_stage=decision_forward token_count={}", tokens.len());
            result["inference_run"] = json!(true);
            match model.probabilities(&tokens, 2).await {
                Ok(probabilities) => {
                    let valid = probabilities.len() == 2
                        && probabilities.iter().all(|p| p.is_finite() && (0.0..=1.0).contains(p))
                        && (probabilities.iter().sum::<f32>() - 1.0).abs() <= 1e-5;
                    if !valid {
                        result["error_code"] = json!("invalid_decision_probabilities");
                        result["responses"] = json!(responses);
                        return Ok((result, 2));
                    }
                    responses.push(json!({"input_tokens": tokens, "probabilities": probabilities}));
                },
                Err(_) => {
                    result["error_code"] = json!("decision_forward_failed");
                    result["responses"] = json!(responses);
                    return Ok((result, 2));
                }
            }
        }
        result["responses"] = json!(responses);
        result["status"] = json!("synthetic_decision_outputs_collected");
        result["peak_memory_usage_bytes"] = json!(engine.peak_memory_usage());
        Ok((result, 0))
    }
}

async fn requested_probe() -> Result<(Value, i32), &'static str> {
    let arguments = std::env::args_os().skip(1).collect::<Vec<_>>();
    if arguments.is_empty() {
        return probe().await;
    }
    if arguments.len() != 2 || arguments[0] != "--decision-model" {
        return Err("expected_explicit_decision_model_path");
    }
    let path = PathBuf::from(&arguments[1]);
    if !path.is_dir() || path.is_symlink() {
        return Err("local_decision_directory_required");
    }
    let backend = std::env::var("UZU_BACKEND").map_err(|_| "explicit_decision_backend_required")?;
    if backend != "cpu" && backend != "vulkan" {
        return Err("decision_backend_must_be_cpu_or_vulkan");
    }
    let context = if backend == "vulkan" {
        eprintln!("probe_stage=vulkan_hardware_admission");
        let (value, code) = probe().await?;
        if code != 0 {
            return Ok((value, code));
        }
        Some(value)
    } else {
        None
    };
    let (mut value, code) = select_backend(DecisionProbe { path, backend }, "decision_backend_unavailable").await?;
    if let Some(context) = context {
        value["hardware_context_probe"] = context;
    }
    Ok((value, code))
}

struct Instance(ash::Instance);
impl Drop for Instance {
    fn drop(&mut self) {
        unsafe { self.0.destroy_instance(None) };
    }
}

async fn probe() -> Result<(Value, i32), &'static str> {
    let entry = unsafe { ash::Entry::load() }.map_err(|_| "vulkan_loader_unavailable")?;
    let version = vk::make_api_version(0, 1, 4, 0);
    let app = vk::ApplicationInfo::default().api_version(version);
    let info = vk::InstanceCreateInfo::default().application_info(&app);
    let instance = Instance(unsafe { entry.create_instance(&info, None) }
        .map_err(|_| "vulkan_1_4_instance_unavailable")?);
    let devices = unsafe { instance.0.enumerate_physical_devices() }
        .map_err(|_| "physical_device_enumeration_failed")?;
    let mut rows = Vec::new();
    let mut eligible = Vec::new();
    for raw in devices {
        let props = unsafe { instance.0.get_physical_device_properties(raw) };
        let name = props.device_name_as_c_str().map_err(|_| "invalid_device_name")?.to_string_lossy();
        let mut row = json!({"name": name, "device_type": format!("{:?}", props.device_type),
            "api_version": props.api_version, "driver_version": props.driver_version,
            "api_version_string": format!("{}.{}.{}", vk::api_version_major(props.api_version),
                vk::api_version_minor(props.api_version), vk::api_version_patch(props.api_version)),
            "eligible": false});
        if props.api_version < version {
            row["rejection_reason"] = json!("vulkan_api_version_below_1_4");
        }
        // Match upstream: older devices must not see the Vulkan 1.4 query structures.
        if props.api_version >= version {
            let candidate = VkPhysicalDevice::new(&entry, &instance.0, raw)
                .map_err(|_| "upstream_device_capability_query_failed")?;
            if let Some(device) = candidate {
                let queue = device.compute_queue_family();
                row["eligible"] = json!(queue.is_some());
                row["compute_queue_family"] = json!(queue);
                row["capability_bits"] = json!(device.capabilities.bits());
                row["compute_units"] = json!(device.compute_units);
                row["subgroup_size"] = json!(device.subgroup_properties.size);
                if queue.is_some() {
                    let priority = match props.device_type {
                        vk::PhysicalDeviceType::DISCRETE_GPU => 0,
                        vk::PhysicalDeviceType::INTEGRATED_GPU => 1,
                        vk::PhysicalDeviceType::VIRTUAL_GPU => 2,
                        vk::PhysicalDeviceType::CPU => 3,
                        _ => 4,
                    };
                    eligible.push((priority, rows.len()));
                }
            }
        }
        rows.push(row);
    }
    eligible.sort_by_key(|&(priority, _)| priority);
    let selected = eligible.first().copied();
    let mut result = json!({"schema_version": "deposium.uzu-vulkan-context-probe/v1",
        "status": "unsupported", "scope": "native_context_only_no_model_or_campaign",
        "actual_backend": "not_observed", "model_loaded": false, "inference_run": false,
        "required_api_version": "1.4.0",
        "native_context_created": false, "devices": rows,
        "engine_selected_device_observed": false,
        "expected_device_selection": selected.map(|(_, index)| index)});
    if !selected.is_some_and(|(priority, _)| priority <= 1) {
        result["error_code"] = json!("no_eligible_discrete_or_integrated_gpu");
        return Ok((result, 3));
    }
    // Calls the public upstream constructor: selection is explicit, with no CPU fallback.
    let engine = Engine::<Vulkan>::new().await.map_err(|_| "native_vulkan_context_creation_failed")?;
    eprintln!("probe_stage=vulkan_context_created");
    result["status"] = json!("context_created");
    result["actual_backend"] = json!("vulkan");
    result["native_context_created"] = json!(true);
    result["peak_memory_usage_bytes"] = json!(engine.peak_memory_usage());
    Ok((result, 0))
}

#[tokio::main(flavor = "current_thread")]
async fn main() {
    let (result, code) = requested_probe().await.unwrap_or_else(|code| (json!({
        "schema_version": "deposium.uzu-vulkan-context-probe/v1", "status": "error",
        "error_code": code, "scope": "native_context_only_no_model_or_campaign",
        "actual_backend": "not_observed", "native_context_created": false,
        "model_loaded": false, "inference_run": false}), 2));
    println!("{result}");
    std::process::exit(code);
}
