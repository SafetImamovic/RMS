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

        /// <summary>Forward speed in m/s. A simulation quantity: never compared unnormalised.</summary>
        public float SpeedMs => Vector3.Dot(_body.linearVelocity, transform.forward);

        /// <summary>Road-wheel angle actually applied, in degrees. Used by the turning-circle check.</summary>
        public float SteerAngleDeg => SteerNorm * profile.steerMaxDeg;

        /// <summary>The calibration this car is running, for the logger and the debug panel.</summary>
        public VehicleProfile Profile => profile;

        /// <summary>How many times the out-of-bounds reset has fired this session.</summary>
        public int ResetCount { get; private set; }

        private void Awake()
        {
            _body = GetComponent<Rigidbody>();
            _body.mass = massKg;

            // Lowering the centre of mass is the single most effective anti-flip measure on a
            // WheelCollider car, and it costs nothing. See FR-010 and SC-006.
            _body.centerOfMass = centreOfMassOffset;

            _spawnPosition = transform.position;
            _spawnRotation = transform.rotation;

            ConfigureSuspension();
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

        private Vector2 ReadMove()
        {
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

            // Torque that produces the profile's acceleration on this mass, split between the
            // two driven wheels. Expressed through the profile rather than as a raw torque so
            // there is exactly one place where "how quickly can this car speed up" is stated.
            float wheelRadius = frontLeft != null ? frontLeft.radius : 0.35f;
            float driveTorque = massKg * profile.accelMs2 * wheelRadius * 0.5f;
            float brakeTorque = massKg * profile.brakeMs2 * wheelRadius * 0.5f;

            // The top speed is a stated constant, not a claim about the dataset (research C3).
            // Cutting torque at the limit rather than clamping the velocity keeps the physics
            // continuous, so the car coasts down instead of hitting an invisible wall.
            bool atTopSpeed = speed >= profile.vMaxMs;
            float motor = (Throttle > 0f && !atTopSpeed) ? Throttle * driveTorque : 0f;
            float braking = Brake * brakeTorque;

            // Reverse: holding brake at a standstill backs the car up slowly, which is what a
            // driver expects and what makes a bad spawn recoverable without a reset.
            if (Brake > 0f && speed < 0.1f)
            {
                motor = -Brake * driveTorque * 0.4f;
                braking = 0f;
            }

            foreach (WheelCollider wheel in Wheels())
            {
                if (wheel == null)
                {
                    continue;
                }

                wheel.brakeTorque = braking;
            }

            if (frontLeft != null) frontLeft.motorTorque = motor;
            if (frontRight != null) frontRight.motorTorque = motor;
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
            Debug.Log($"[CarController] out of bounds ({(fell ? "fell" : "strayed")}), reset #{ResetCount}");
        }

        /// <summary>Put the car back at its spawn point, stopped and straight.</summary>
        public void ResetToSpawn()
        {
            _body.linearVelocity = Vector3.zero;
            _body.angularVelocity = Vector3.zero;
            transform.SetPositionAndRotation(_spawnPosition, _spawnRotation);
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
