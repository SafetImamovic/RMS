using UnityEngine;
using UnityEngine.InputSystem;

namespace SelfDrivingSim.Vehicle
{
    /// <summary>
    /// Keyboard-drivable car whose every limit comes from <see cref="VehicleProfile"/>.
    ///
    /// The point of this component is not that the car moves. It is that it moves the way
    /// the recorded human data says a car in this simulator moves: the steering spans the
    /// same range, it travels at a rate a person can produce comparable driving with, and
    /// the full-lock turning circle matches the documented minimum radius. Everything
    /// downstream inherits this car, so a limit that is wrong here does not surface as a
    /// bug later, it quietly invalidates the M5 comparison.
    ///
    /// Physics is the primary model (DESIGN 4.2), four WheelColliders on a Rigidbody. The
    /// simplified kinematic fallback is adopted only if StabilityMonitor's three conditions
    /// fire on three consecutive drives (research C5), never on the strength of "it felt
    /// wrong".
    ///
    /// Controls: W and S throttle and brake, A and D steer.
    /// </summary>
    [RequireComponent(typeof(Rigidbody))]
    public class CarController : MonoBehaviour
    {
        [Header("Calibration")]
        [Tooltip("Every limit the car has. Mirrors python/track/config.py; checked by VehicleProfileMirrorTests.")]
        [SerializeField]
        private VehicleProfile profile = new VehicleProfile();

        [Header("Wheels (front two steer and drive)")]
        [SerializeField] private WheelCollider frontLeft;
        [SerializeField] private WheelCollider frontRight;
        [SerializeField] private WheelCollider rearLeft;
        [SerializeField] private WheelCollider rearRight;

        [Tooltip("Optional visual meshes, one per wheel in the same order. May be left empty.")]
        [SerializeField] private Transform frontLeftMesh;
        [SerializeField] private Transform frontRightMesh;
        [SerializeField] private Transform rearLeftMesh;
        [SerializeField] private Transform rearRightMesh;

        [Tooltip("Rotation applied on top of the WheelCollider pose before it reaches the mesh.\n\n" +
                 "GetWorldPose returns a rotation whose axle runs along local X. A Unity cylinder's " +
                 "axis runs along its local Y, so it needs 90 degrees about Z to lie down as a wheel. " +
                 "Without this the pose overwrites the authored rotation on the first physics step " +
                 "and the wheels stand up like barrels. Set this to zero when using an imported " +
                 "wheel model that is already oriented correctly.")]
        [SerializeField]
        private Vector3 wheelMeshRotationOffset = new Vector3(0f, 0f, 90f);

        [Header("Body")]
        [Tooltip("Mass in kg. A small passenger car.")]
        [SerializeField] private float massKg = 1200f;

        [Tooltip("Centre of mass offset from the body origin, in local metres. The Y value is " +
                 "what keeps the car from flipping in a full-lock turn at top speed (FR-010): " +
                 "a Rigidbody's default centre sits at the collider centre, which is far too high " +
                 "for a car. Lower it before blaming the wheel friction.")]
        [SerializeField]
        private Vector3 centreOfMassOffset = new Vector3(0f, -0.6f, 0f);

        [Tooltip("How much longitudinal grip the tyres get beyond what the profile actually " +
                 "demands. 1.0 means the tyre is exactly at its limit under full throttle, " +
                 "which is the condition that had the wheels spinning at 8 m/s of slip. Two " +
                 "keeps the tyre near the friction curve's peak instead of out on its " +
                 "asymptote. Raising this does not make the car faster: top speed and " +
                 "acceleration are set by the profile, and this only decides whether the " +
                 "tyre can deliver them.")]
        [SerializeField] private float gripSafetyFactor = 2f;

        [Tooltip("Slip the wheels are expected to stay under in normal driving, in m/s. " +
                 "Nothing acts on this: it is the yardstick the startup log compares the " +
                 "friction correction per substep against, so that a change to wheel mass, " +
                 "grip or substep count can be judged before driving rather than after.")]
        [SerializeField] private float slipCeilingMs = 1f;

        [Header("Input")]
        [Tooltip("Optional. If assigned, the Player/Move action is used. If left empty the " +
                 "component reads W/A/S/D from the keyboard directly, which is what the " +
                 "quickstart documents.")]
        [SerializeField]
        private InputActionAsset inputActions;

        [Header("Bounds (FR-012)")]
        [Tooltip("Distance from the spawn point past which the car is reset. The flat plane " +
                 "has no edges, so without this a test run ends with the car falling forever.")]
        [SerializeField]
        private float boundsRadiusM = 250f;

        [Tooltip("Height below the spawn point that counts as having fallen through the world.")]
        [SerializeField]
        private float fallResetM = 10f;

        private Rigidbody _body;
        private InputAction _moveAction;
        private Vector3 _spawnPosition;
        private Quaternion _spawnRotation;

        /// <summary>Current steering, normalised to [-1, 1]. What the drive log records.</summary>
        public float SteerNorm { get; private set; }

        /// <summary>Throttle in [0, 1], in the dataset's own column terms.</summary>
        public float Throttle { get; private set; }

        /// <summary>Brake in [0, 1], in the dataset's own column terms.</summary>
        public float Brake { get; private set; }

        /// <summary>Forward speed in m/s. A simulation quantity: never compared unnormalised.
        ///
        /// This is the projection of the velocity onto the car's nose, which is the quantity
        /// the dataset's own speed column corresponds to and therefore the one the drive log
        /// records. It is NOT the right quantity to govern the top speed with: see
        /// <see cref="SpeedMagnitudeMs"/>.
        /// </summary>
        public float SpeedMs => Vector3.Dot(_body.linearVelocity, transform.forward);

        /// <summary>
        /// How fast the car is actually travelling over the ground, regardless of where it
        /// is pointing. Vertical motion is excluded so that falling does not read as speed.
        ///
        /// The distinction matters because the two can disagree. <see cref="SpeedMs"/> is a
        /// projection, so it is smaller than the truth whenever the car is not travelling
        /// exactly where it points, and it is the smaller number that a governor comparing
        /// against the top speed would see. Governing on the projection lets the car exceed
        /// its own stated maximum: the first keyboard drive reached 16.2 m/s against a
        /// stated 10.0, spending 25 of 91 seconds above the limit.
        /// </summary>
        public float SpeedMagnitudeMs
        {
            get
            {
                Vector3 planar = _body.linearVelocity;
                planar.y = 0f;
                return planar.magnitude;
            }
        }

        /// <summary>Road-wheel angle actually applied, in degrees. Used by the turning-circle check.</summary>
        public float SteerAngleDeg => SteerNorm * profile.steerMaxDeg;

        /// <summary>The calibration this car is running, for the logger and the debug panel.</summary>
        public VehicleProfile Profile => profile;

        /// <summary>Drive torque commanded on the last physics step, N m per driven wheel.</summary>
        public float LastMotorTorque { get; private set; }

        /// <summary>
        /// The top-speed taper on the last physics step: 1 means full torque is allowed,
        /// 0 means the governor is holding it shut.
        /// </summary>
        public float LastHeadroom { get; private set; }

        /// <summary>How many times the out-of-bounds reset has fired this session.</summary>
        public int ResetCount { get; private set; }

        /// <summary>
        /// Resets caused by the car dropping below the world, counted apart from the ones
        /// caused by wandering off the plane. StabilityMonitor treats only the first kind as
        /// a physics failure: straying is a driver going too far, falling is the ground
        /// failing to hold the car (research C5, condition 3).
        /// </summary>
        public int FallResetCount { get; private set; }

        /// <summary>Resets caused by leaving the bounds radius. Driver error, not instability.</summary>
        public int StrayResetCount { get; private set; }

        /// <summary>
        /// How many of the four wheels are touching the ground this physics step.
        ///
        /// Written without <see cref="Wheels"/> because this is read every FixedUpdate and
        /// that helper allocates a fresh array on each call.
        /// </summary>
        public int GroundedWheelCount
        {
            get
            {
                int n = 0;
                if (frontLeft != null && frontLeft.isGrounded) n++;
                if (frontRight != null && frontRight.isGrounded) n++;
                if (rearLeft != null && rearLeft.isGrounded) n++;
                if (rearRight != null && rearRight.isGrounded) n++;
                return n;
            }
        }

        private void Awake()
        {
            _body = GetComponent<Rigidbody>();
            _body.mass = massKg;

            // Smooth the car's RENDERED motion between physics steps.
            //
            // Physics runs at 50 Hz and the display refreshes faster, so without this some
            // frames show a new position and some repeat the previous one. The unevenness
            // reads as jitter, and it was reported as such the first time the car was driven
            // on a track: on the open plane there was nothing close enough to judge motion
            // against, while barriers a few metres away make it obvious.
            //
            // The drive log is unaffected, which is the reason this is safe. Interpolation
            // changes what the transform reports during Update, not during FixedUpdate, and
            // DriveLogger samples in FixedUpdate. The measurements stay the physics truth
            // while the picture stops stuttering.
            _body.interpolation = RigidbodyInterpolation.Interpolate;

            // Lowering the centre of mass is the single most effective anti-flip measure on a
            // WheelCollider car, and it costs nothing. See FR-010 and SC-006.
            _body.centerOfMass = centreOfMassOffset;

            _spawnPosition = transform.position;
            _spawnRotation = transform.rotation;

            ConfigureSuspension();
            ConfigureTyreGrip();
        }

        private void OnEnable()
        {
            if (inputActions == null)
            {
                return;
            }

            _moveAction = inputActions.FindAction("Player/Move");
            _moveAction?.Enable();
        }

        private void OnDisable()
        {
            _moveAction?.Disable();
        }

        /// <summary>
        /// Give the suspension a spring stiff enough to carry this mass.
        /// The WheelCollider default is tuned for a much lighter body, and a car that sinks
        /// into the plane on the first frame is the most common first-day symptom.
        /// </summary>
        private void ConfigureSuspension()
        {
            foreach (WheelCollider wheel in Wheels())
            {
                if (wheel == null)
                {
                    continue;
                }

                JointSpring spring = wheel.suspensionSpring;
                // A quarter of the body weight per corner, times a comfortable factor.
                spring.spring = massKg * 9.81f * 0.25f * 12f;
                spring.damper = spring.spring * 0.12f;
                spring.targetPosition = 0.5f;
                wheel.suspensionSpring = spring;

                wheel.suspensionDistance = 0.25f;
                wheel.forceAppPointDistance = 0.1f;
            }
        }

        /// <summary>
        /// Give the tyres enough longitudinal grip to actually deliver the profile's
        /// acceleration, instead of spinning.
        ///
        /// The WheelCollider default forward curve peaks at a friction coefficient of 1 and
        /// then DECAYS to 0.5 once slip passes 0.8. That asymptote is the number that matters,
        /// because a wheel which has already broken traction is sitting on it. A quarter of
        /// this car's weight is 2943 N, so the asymptote offers 1471 N per wheel, and driving
        /// all four to 5 m/s^2 asks for 1500 N. Being two percent short is enough: the tyre
        /// finds an equilibrium spinning 8 m/s faster than the road and stays there. It was
        /// measured at 7.97 to 8.80 m/s of slip across four separate drives, near-constant
        /// regardless of speed or steering, which is what an equilibrium looks like.
        ///
        /// The stiffness is derived from the profile rather than typed in, so that when T024
        /// settles accelMs2 and brakeMs2 the tyre stops being the binding constraint on its
        /// own. Otherwise every future change to those numbers would silently reintroduce this.
        ///
        /// Sideways friction is deliberately left at its default. Nothing measured says it is
        /// wrong, and raising lateral grip works directly against the anti-flip requirement
        /// (FR-010, SC-006) that T025 exists to test. One change at a time is also the only
        /// reason this cause was found: three earlier theories about the same symptom were
        /// argued from the car's response and all three were wrong.
        /// </summary>
        private void ConfigureTyreGrip()
        {
            if (profile == null)
            {
                return;
            }

            // The friction coefficient the tyre has to sustain for the profile to be
            // achievable. Braking is included because it is the larger demand on most cars.
            float requiredMu = Mathf.Max(profile.accelMs2, profile.brakeMs2) / 9.81f;
            float applied = 0f;

            // Substep the tyre solver. This is the change that actually settles the wheels,
            // and it is worth being precise about why, because two earlier fixes aimed at the
            // wrong thing.
            //
            // A friction impulse changes wheel surface speed by 2*F*dt/(m_wheel*r) in one
            // step. With the stock curve that is 2*1471*0.02/(20*0.35) = 8.4 m/s, and after
            // the stiffness was raised it became 20.1 m/s. Those are not incidental numbers:
            // the measured "slip" was 8 m/s before and swung between 1 and 23 m/s after. The
            // wheel was never spinning up against grip, it was overshooting the correction and
            // being thrown back past it, every step, with ZERO drive torque applied. Traction
            // control cannot touch that, because there is no demand to withdraw.
            //
            // Substeps divide dt for the wheel solver alone, leaving the rest of the physics
            // at its normal rate, so the correction per substep drops by the same factor
            // without making the whole simulation more expensive or changing the log rate.
            // Thirty substeps put it near 0.7 m/s, comfortably inside the slip ceiling that
            // traction control watches.
            //
            // Set on any one WheelCollider; it applies to the whole vehicle.
            if (frontLeft != null)
            {
                frontLeft.ConfigureVehicleSubsteps(
                    speedThreshold: 5f, stepsBelowThreshold: 30, stepsAboveThreshold: 30);
            }

            foreach (WheelCollider wheel in Wheels())
            {
                if (wheel == null)
                {
                    continue;
                }

                WheelFrictionCurve forward = wheel.forwardFriction;
                if (forward.asymptoteValue <= 0f)
                {
                    continue;
                }

                // Never below 1: this is a floor on grip, not a rescaling of it, so a profile
                // asking for very little must not end up with tyres worse than stock.
                forward.stiffness = Mathf.Max(
                    1f, gripSafetyFactor * requiredMu / forward.asymptoteValue);
                wheel.forwardFriction = forward;
                applied = forward.stiffness;
            }

            // Stated once per run. Whether this method ran at all was an assumption during
            // the wheelspin work, and an assumption about your own fix is the expensive kind.
            // The predicted friction correction per substep, which is the quantity that decides
            // whether the wheel settles or oscillates. Printed so a future change to mass,
            // grip or substeps can be judged before driving rather than after.
            float wheelMass = frontLeft != null ? frontLeft.mass : 20f;
            float radius = frontLeft != null ? frontLeft.radius : 0.35f;
            float load = massKg * 9.81f * 0.25f;
            float perSubstep =
                2f * load * 0.5f * applied * Time.fixedDeltaTime / (30f * wheelMass * radius);

            Debug.Log($"[CarController] forward tyre stiffness {applied:F3} " +
                      $"(requiredMu {requiredMu:F3}, safety {gripSafetyFactor:F2}), " +
                      $"friction correction {perSubstep:F2} m/s per substep against a slip " +
                      $"budget of {slipCeilingMs:F2} m/s. The correction must stay well under " +
                      $"the budget or the wheels oscillate instead of settling.");
        }

        private void Update()
        {
            Vector2 move = ReadMove();

            // Steering ramps toward the held direction rather than snapping to it. The rate
            // is a calibration value: research C4 treats the dataset's full-range-in-one-frame
            // jumps as evidence about the KEYBOARD used to record it, not as a vehicle
            // capability. A car that reproduced them would be unsteerable. T023 settles the
            // rate by measuring a real drive against the human P95.
            float target = Mathf.Clamp(move.x, -1f, 1f);
            SteerNorm = Mathf.MoveTowards(
                SteerNorm,
                target,
                profile.steerRateNormPerS * Time.deltaTime);

            float longitudinal = Mathf.Clamp(move.y, -1f, 1f);
            Throttle = Mathf.Max(0f, longitudinal);
            Brake = Mathf.Max(0f, -longitudinal);
        }

        private void FixedUpdate()
        {
            ApplySteering();
            ApplyDrive();
            UpdateWheelMeshes();
            EnforceBounds();
        }

        /// <summary>
        /// When set, this replaces the keyboard for one frame's worth of input. X is steering
        /// and Y is throttle above zero, brake below, exactly as ReadMove returns them.
        ///
        /// This exists so the calibration manoeuvres can be run without a person holding a
        /// key. T022, T024 and T025 are all specified as fixed inputs (full lock, full
        /// throttle, full brake), so driving them by hand measures how steadily the key was
        /// held as much as it measures the car, and the resulting numbers go into DESIGN.md.
        /// Scripting them makes those figures reproducible, which Principle VI asks for.
        ///
        /// T023 deliberately does NOT use this. It compares human keyboard steering against
        /// the human dataset (FR-005, SC-002); a scripted drive would only measure the script.
        /// </summary>
        public Vector2? ScriptedMove { get; set; }

        private Vector2 ReadMove()
        {
            if (ScriptedMove.HasValue)
            {
                return ScriptedMove.Value;
            }

            if (_moveAction != null)
            {
                return _moveAction.ReadValue<Vector2>();
            }

            Keyboard keyboard = Keyboard.current;
            if (keyboard == null)
            {
                return Vector2.zero;
            }

            float x = 0f;
            float y = 0f;
            if (keyboard.aKey.isPressed || keyboard.leftArrowKey.isPressed) x -= 1f;
            if (keyboard.dKey.isPressed || keyboard.rightArrowKey.isPressed) x += 1f;
            if (keyboard.wKey.isPressed || keyboard.upArrowKey.isPressed) y += 1f;
            if (keyboard.sKey.isPressed || keyboard.downArrowKey.isPressed) y -= 1f;
            return new Vector2(x, y);
        }

        private void ApplySteering()
        {
            float angle = SteerAngleDeg;
            if (frontLeft != null) frontLeft.steerAngle = angle;
            if (frontRight != null) frontRight.steerAngle = angle;
        }

        private void ApplyDrive()
        {
            float speed = SpeedMs;

            // Torque that produces the profile's acceleration on this mass. Expressed through
            // the profile rather than as a raw torque so there is exactly one place where
            // "how quickly can this car speed up" is stated.
            //
            // Split across all FOUR wheels, not two.
            //
            // Two-wheel drive asks each front tyre for mass*accel/2 = 3000 N, while a wheel
            // on a 1200 kg car carries about 1200*9.81/4 = 2943 N of load, and less than
            // that at the front once weight shifts rearward under acceleration. Demanding
            // more force than the tyre has load to produce is the definition of wheelspin,
            // and a measured drive showed exactly that: wheels turning at 18.5 m/s under a
            // body doing 10, with 10.8 m/s of slip, and acceleration collapsed to 0.1-1.5
            // m/s^2 against a profile that asks for 5.0. Spinning tyres do not accelerate a
            // car, they just store energy that surfaces later as an over-speed.
            //
            // Across four wheels the demand is 1500 N each, comfortably inside the available
            // load, so the torque reaches the road instead of the tyre.
            float wheelRadius = frontLeft != null ? frontLeft.radius : 0.35f;
            float driveTorque = massKg * profile.accelMs2 * wheelRadius * 0.25f;
            float brakeTorque = massKg * profile.brakeMs2 * wheelRadius * 0.25f;

            // The top speed is a stated constant, not a claim about the dataset (research C3).
            // Cutting torque at the limit rather than clamping the velocity keeps the physics
            // continuous, so the car coasts down instead of hitting an invisible wall.
            //
            // Governed on the ACTUAL ground speed, not on the forward projection. The two
            // differ whenever the car is not travelling exactly where it points, and the
            // projection is always the smaller of the pair, so a governor watching it lets
            // the car through. Measured on the first keyboard drive: 16.2 m/s reached
            // against a stated maximum of 10.0.
            float actualSpeed = SpeedMagnitudeMs;

            // Torque tapers to nothing over the last tenth of the speed range instead of
            // being switched off at the limit. An on/off cut is a bang-bang controller: the
            // car crosses the limit, loses all torque, drops below it, regains full torque,
            // and repeats every physics step. That chatter is visible while driving and it
            // puts a spurious oscillation into the logged speed, which then lands in the
            // per-frame speed-change distribution that FR-007 is measured on.
            // Governed on the faster of the body and the DRIVEN WHEELS.
            //
            // Watching the body alone does not work, and the drive log shows exactly why: at
            // t=5.0 the throttle went to zero, the commanded torque went to zero, and the car
            // kept accelerating from 7.9 to 11.2 m/s on flat ground before stopping dead and
            // coasting. Nothing was pushing it except its own wheels.
            //
            // 1050 N m into a wheel of inertia 0.5*20*0.35^2 = 1.225 kg m^2 is an angular
            // acceleration of 857 rad/s^2, so the wheels outrun the road badly. That surplus
            // spin is stored energy, and tyre friction hands it back to the car after the
            // torque is cut: the body coasts UP to whatever speed the wheels were doing. The
            // wheels, not the body, decide the terminal speed, so they are what the limit has
            // to be applied to.
            float wheelSurfaceSpeed = DrivenWheelSurfaceSpeedMs(wheelRadius);
            float governing = Mathf.Max(actualSpeed, wheelSurfaceSpeed);

            float taperFrom = profile.vMaxMs * 0.9f;
            float headroom = Mathf.InverseLerp(profile.vMaxMs, taperFrom, governing);
            float motor = Throttle > 0f ? Throttle * driveTorque * headroom : 0f;
            float braking = Brake * brakeTorque;

            // There is deliberately no traction control here.
            //
            // A slip-based torque cut was added while the wheels were oscillating, on the
            // theory that the drive was overpowering the tyre. Substepping the wheel solver
            // fixed the oscillation outright, and the run that proved it also convicted the
            // traction control: it was still cutting 32 percent of the torque at 8 m/s, in
            // response to 0.3 to 0.5 m/s of slip. That much slip is not a fault. It is the
            // slip a tyre needs in order to generate force at all, so cutting torque in
            // response to it taxes the car for working correctly, and acceleration fell from
            // 4.81 to 3.23 m/s^2 across the speed range because of it.
            //
            // Removed rather than widened. Its purpose was to contain a runaway that does not
            // happen, and machinery kept "just in case" is machinery nobody can later explain.

            WarnIfGovernorLate(actualSpeed);

            // Reverse: holding brake at a standstill backs the car up slowly, which is what a
            // driver expects and what makes a bad spawn recoverable without a reset.
            //
            // The speed condition is on the signed forward speed, because reversing is a
            // direction and not a magnitude. The extra bound is a separate matter: without
            // it, reverse torque was applied for as long as the key was held, with no limit
            // of any kind, because the top-speed test above only ever looked at going
            // forward. Reverse is capped at half of the forward maximum.
            if (Brake > 0f && speed < 0.1f && actualSpeed < profile.vMaxMs * 0.5f)
            {
                motor = -Brake * driveTorque * 0.4f;
                braking = 0f;
            }

            // Recorded AFTER the reverse branch, which is the last thing that can change the
            // commanded torque. Recording it earlier would log a reversing car as coasting.
            //
            // The drive log carries the controller's output, not just the car's response,
            // because three separate explanations for the car exceeding its top speed were
            // argued from the response alone and all three were wrong.
            LastMotorTorque = motor;
            LastHeadroom = headroom;

            foreach (WheelCollider wheel in Wheels())
            {
                if (wheel == null)
                {
                    continue;
                }

                wheel.brakeTorque = braking;
                wheel.motorTorque = motor;
            }
        }

        /// <summary>
        /// How fast the driven wheels' contact patches are moving, in m/s.
        ///
        /// This is the speed the car is being driven towards. It exceeds the body speed
        /// whenever the wheels are slipping, and the difference is energy stored in their
        /// rotation that will be handed back to the car later.
        /// </summary>
        private float DrivenWheelSurfaceSpeedMs(float wheelRadius)
        {
            // All four are driven, so all four are watched.
            float rpm = 0f;
            if (frontLeft != null) rpm = Mathf.Max(rpm, Mathf.Abs(frontLeft.rpm));
            if (frontRight != null) rpm = Mathf.Max(rpm, Mathf.Abs(frontRight.rpm));
            if (rearLeft != null) rpm = Mathf.Max(rpm, Mathf.Abs(rearLeft.rpm));
            if (rearRight != null) rpm = Mathf.Max(rpm, Mathf.Abs(rearRight.rpm));
            return rpm * 2f * Mathf.PI * wheelRadius / 60f;
        }

        /// <summary>Surface speed of the driven wheels, for the drive log.</summary>
        public float WheelSurfaceSpeedMs =>
            DrivenWheelSurfaceSpeedMs(frontLeft != null ? frontLeft.radius : 0.35f);

        private bool _governorReported;

        /// <summary>
        /// Report, once per run, the speed at which the car actually stopped accelerating.
        ///
        /// A drive measured 15.09 m/s against a stated maximum of 10.0, and the log showed a
        /// clean constant acceleration straight through the limit that only stopped at
        /// 14.06 m/s. That shape says the governor is working and comparing against the
        /// wrong number, which is a different fault from the governor not running at all,
        /// and the two are indistinguishable from the outside.
        ///
        /// So the car states what it believes its own limit to be, next to the speed it
        /// reached. If those disagree, the profile reaching the physics is not the profile
        /// in vehicle_profile.json.
        /// </summary>
        private void WarnIfGovernorLate(float actualSpeed)
        {
            if (_governorReported || actualSpeed <= profile.vMaxMs * 1.05f)
            {
                return;
            }

            _governorReported = true;
            Debug.LogError(
                $"[CarController] travelling at {actualSpeed:F2} m/s with a stated maximum " +
                $"of {profile.vMaxMs:F2} m/s (profile: wheelbase {profile.wheelbaseM}, " +
                $"steerMax {profile.steerMaxDeg}, accel {profile.accelMs2}, " +
                $"steerRate {profile.steerRateNormPerS}). Physics step " +
                $"{Time.fixedDeltaTime:F4}s, timeScale {Time.timeScale}.");
        }

        private void UpdateWheelMeshes()
        {
            Quaternion offset = Quaternion.Euler(wheelMeshRotationOffset);
            SyncMesh(frontLeft, frontLeftMesh, offset);
            SyncMesh(frontRight, frontRightMesh, offset);
            SyncMesh(rearLeft, rearLeftMesh, offset);
            SyncMesh(rearRight, rearRightMesh, offset);
        }

        private static void SyncMesh(WheelCollider wheel, Transform mesh, Quaternion offset)
        {
            if (wheel == null || mesh == null)
            {
                return;
            }

            wheel.GetWorldPose(out Vector3 position, out Quaternion rotation);
            // Offset applied on the right so it composes in the wheel's own frame: steering
            // yaw and rolling spin still come from the pose, the offset only lies the
            // cylinder down onto its axle.
            mesh.SetPositionAndRotation(position, rotation * offset);
        }

        /// <summary>
        /// FR-012. The flat plane has no edges, so a run that wanders off it would otherwise
        /// end with the car falling indefinitely and the acceptance test never finishing.
        /// </summary>
        private void EnforceBounds()
        {
            Vector3 offset = transform.position - _spawnPosition;
            bool strayed = offset.magnitude > boundsRadiusM;
            bool fell = offset.y < -fallResetM;

            if (!strayed && !fell)
            {
                return;
            }

            ResetToSpawn();
            ResetCount++;
            if (fell)
            {
                FallResetCount++;
            }
            else
            {
                StrayResetCount++;
            }

            Debug.Log($"[CarController] out of bounds ({(fell ? "fell" : "strayed")}), reset #{ResetCount}");
        }

        /// <summary>
        /// Move the car somewhere and treat that as its new spawn point.
        ///
        /// The spawn is captured in Awake, and both the out-of-bounds reset (FR-012) and
        /// <see cref="ResetToSpawn"/> return the car to whatever was captured then. Teleporting
        /// the car without telling it - which is what a randomised start does (T058) - leaves
        /// those two pointing at the old position, so the first reset of the run drags the car
        /// back to wherever the scene happened to place it, most likely off the track
        /// entirely.
        /// </summary>
        public void SetSpawn(Vector3 position, Quaternion rotation)
        {
            _spawnPosition = position;
            _spawnRotation = rotation;
            ResetToSpawn();
        }

        /// <summary>Put the car back at its spawn point, stopped and straight.</summary>
        /// <remarks>
        /// The pose goes onto the <b>Rigidbody</b>, not only the Transform. With
        /// <see cref="RigidbodyInterpolation.Interpolate"/> set in Awake the body owns the pose
        /// and drives the Transform between physics steps, so writing the Transform alone is
        /// discarded on the next step and the car snaps back to wherever the body already was.
        /// That failure is close to invisible: the scene positions the car on seed 1's first
        /// checkpoint, so on seed 1 the snap-back lands on the road and everything looks right,
        /// while every other seed puts the car down outside its own track and it falls through
        /// the world about a second later.
        ///
        /// Interpolation is switched off across the move and restored after. A teleport with it
        /// left on is smeared from the old pose to the new one, which reads as the car flying
        /// across the map rather than being placed.
        /// </remarks>
        public void ResetToSpawn()
        {
            _body.linearVelocity = Vector3.zero;
            _body.angularVelocity = Vector3.zero;

            RigidbodyInterpolation previous = _body.interpolation;
            _body.interpolation = RigidbodyInterpolation.None;
            _body.position = _spawnPosition;
            _body.rotation = _spawnRotation;
            transform.SetPositionAndRotation(_spawnPosition, _spawnRotation);
            _body.interpolation = previous;

            SteerNorm = 0f;
            Throttle = 0f;
            Brake = 0f;

            foreach (WheelCollider wheel in Wheels())
            {
                if (wheel == null)
                {
                    continue;
                }

                wheel.motorTorque = 0f;
                wheel.brakeTorque = 0f;
                wheel.steerAngle = 0f;
            }
        }

        private WheelCollider[] Wheels()
        {
            return new[] { frontLeft, frontRight, rearLeft, rearRight };
        }
    }
}
