using System;
using UnityEngine;
using UnityEngine.InputSystem;

namespace SelfDrivingSim.Environment
{
    /// <summary>How a view places itself. The three behaviours the rig knows.</summary>
    public enum ViewKind
    {
        /// <summary>Rigidly attached to the car. Mouse look is a bounded offset that recentres.</summary>
        FirstPerson,

        /// <summary>Chase from behind. Yaw follows the car with lag; the mouse does not steer it.</summary>
        ChaseLocked,

        /// <summary>Free orbit in polar coordinates. The mouse owns yaw and pitch outright.</summary>
        FreeOrbit,

        /// <summary>
        /// Detached from the car entirely: fly it yourself, like a scene view.
        ///
        /// **The only view that does not follow anything.** Every other kind is anchored to the
        /// car's transform, which is what makes them useless for looking at the track ahead of the
        /// agent, at a corner it has not reached, or at the barrier it just clipped. This one keeps
        /// its own position and the car may leave the frame, which is the point rather than a
        /// defect.
        /// </summary>
        FreeFly,
    }

    /// <summary>One camera view: where it sits and how it behaves.</summary>
    [Serializable]
    public class CameraView
    {
        [Tooltip("Shown in the log when the view is switched.")]
        public string name = "View";

        public ViewKind kind = ViewKind.ChaseLocked;

        [Tooltip("Point on the car this view is built around, in the car's local frame. " +
                 "For FirstPerson it IS the camera position; for the chase views it is what " +
                 "the camera looks at.")]
        public Vector3 pivotOffset = new Vector3(0f, 1.0f, 0f);

        [Tooltip("Distance from the pivot. Ignored by FirstPerson.")]
        public float distanceM = 8f;

        [Tooltip("Elevation above the pivot, in degrees. The starting pitch for FreeOrbit.")]
        public float pitchDeg = 14f;

        [Tooltip("Vertical field of view. Narrower reads as faster; Forza-style bumper cams " +
                 "run wide to exaggerate speed.")]
        public float fovDeg = 60f;

        [Tooltip("Degrees per second the chase yaw chases the car's heading. Lower lags more, " +
                 "which reads as weight. Ignored by FreeOrbit, which the mouse owns.")]
        public float yawFollowPerSecond = 6f;

        [Tooltip("Seconds for the position to catch up. Zero is rigid, which is what a " +
                 "first-person view wants.")]
        public float followSmoothTime = 0.08f;

        public float minDistanceM = 2f;
        public float maxDistanceM = 25f;
    }

    /// <summary>
    /// Multi-view driving camera: cockpit, bumper, two chase distances and a free orbit,
    /// switched the way a racing game switches them.
    ///
    /// The camera is deliberately NOT a child of the car. Parenting makes a camera inherit
    /// the car's yaw, which is exactly what stops a free orbit from being free. Views that
    /// DO want to ride with the body (the first-person ones) get that by construction here,
    /// under their own control, rather than from the transform hierarchy.
    ///
    /// This is a driving aid and nothing more. It touches none of the observations CarAgent
    /// will expose in User Story 3, which come from raycasts and vehicle state, so this file
    /// can be retuned, replaced or deleted without moving a single number in the feature.
    ///
    /// Controls: mouse orbits or looks, wheel zooms, C cycles views, 1 to 6 pick one
    /// directly, Escape releases the cursor.
    ///
    /// View 6 is a free fly camera: WASD moves it, Q and E drop and lift it, Shift is a boost,
    /// and the mouse aims it. It is detached from the car, so the car can leave the frame.
    /// **WASD also drives the car when a human is at the wheel**, so the free fly is meant for
    /// watching a policy or the scripted driver, where the keyboard reaches nothing else.
    /// </summary>
    public class CameraRig : MonoBehaviour
    {
        [Header("Target")]
        [SerializeField] private Transform target;

        [Header("Views, in switch order")]
        [SerializeField]
        private CameraView[] views =
        {
            new CameraView
            {
                name = "Cockpit",
                kind = ViewKind.FirstPerson,
                // Driver's eye: left of centre, ahead of the wheelbase midpoint.
                // The body box is 1.8 x 0.6 x 4.0 m centred 0.5 m up in the car's frame, so
                // it spans local y 0.2 to 0.8 and local z -2.0 to 2.0. Two constraints follow.
                // Inside the box the camera renders back faces and goes black. Only just
                // above it, the roof stretches to the horizon and hides the road: at 0.15 m
                // of clearance the bonnet covers half the screen. Sitting 0.45 m above the
                // roof and 0.9 m forward drops the body to the lower fifth of the frame,
                // which reads as a bonnet rather than a wall.
                pivotOffset = new Vector3(-0.35f, 1.25f, 0.9f),
                fovDeg = 70f,
                followSmoothTime = 0f,
            },
            new CameraView
            {
                name = "Bumper",
                kind = ViewKind.FirstPerson,
                // Just ahead of the nose: the body ends at local z = 2.0, so anything less
                // than that puts the camera inside the mesh.
                pivotOffset = new Vector3(0f, 0.45f, 2.15f),
                // Wide and low. This is the view that makes 10 m/s feel like a speed.
                fovDeg = 82f,
                followSmoothTime = 0f,
            },
            new CameraView
            {
                name = "Chase near",
                kind = ViewKind.ChaseLocked,
                pivotOffset = new Vector3(0f, 1.0f, 0f),
                distanceM = 6.5f,
                pitchDeg = 12f,
                yawFollowPerSecond = 7f,
            },
            new CameraView
            {
                name = "Chase far",
                kind = ViewKind.ChaseLocked,
                pivotOffset = new Vector3(0f, 1.2f, 0f),
                distanceM = 11f,
                pitchDeg = 18f,
                yawFollowPerSecond = 4.5f,
            },
            new CameraView
            {
                name = "Free orbit",
                kind = ViewKind.FreeOrbit,
                pivotOffset = new Vector3(0f, 1.0f, 0f),
                distanceM = 8f,
                pitchDeg = 14f,
            },
            new CameraView
            {
                name = "Free fly",
                kind = ViewKind.FreeFly,
                // Starts where a chase camera would, so pressing 6 does not teleport the view
                // somewhere unrecognisable. From there it is yours.
                pivotOffset = new Vector3(0f, 1.0f, 0f),
                distanceM = 10f,
                pitchDeg = 16f,
                fovDeg = 60f,
            },
        };

        [SerializeField] private int startViewIndex = 2;

        [Header("Mouse")]
        [SerializeField] private float yawDegPerPixel = 0.16f;
        [SerializeField] private float pitchDegPerPixel = 0.12f;
        [SerializeField] private bool invertPitch = false;
        [SerializeField] private float minPitchDeg = -5f;
        [SerializeField] private float maxPitchDeg = 80f;

        [Tooltip("How far a first-person view may look away from straight ahead, in degrees.")]
        [SerializeField]
        private float firstPersonYawLimitDeg = 120f;

        [SerializeField] private float firstPersonPitchLimitDeg = 45f;

        [Header("Zoom")]
        [Tooltip("Metres per wheel notch. Applies to the chase and orbit views; the " +
                 "first-person views have no distance to change.")]
        [SerializeField]
        private float zoomMetresPerNotch = 1.2f;

        [Header("Free fly (view 6)")]
        [Tooltip("Metres per second the free fly camera moves on WASD, before the boost.")]
        [SerializeField]
        private float flySpeedMs = 12f;

        [Tooltip("Multiplier while Shift is held. A track is roughly 200 m round, so crossing it " +
                 "at walking pace is not useful.")]
        [SerializeField]
        private float flyBoostFactor = 4f;

        [Tooltip("Seconds for the fly velocity to catch up to the keys. Zero is instant and " +
                 "reads as twitchy on a wide shot.")]
        [SerializeField]
        private float flySmoothTime = 0.10f;

        [Header("Recentre")]
        [Tooltip("Seconds of mouse stillness before a free orbit eases back behind the car, " +
                 "and before a first-person view returns to looking straight ahead.")]
        [SerializeField]
        private float recentreDelayS = 1.5f;

        [Tooltip("Speed in m/s below which the car counts as parked and a free orbit stops " +
                 "recentring. Without this the camera fights you while manoeuvring slowly.")]
        [SerializeField]
        private float recentreMinSpeedMs = 2.0f;

        [SerializeField] private float recentreDegPerSecond = 90f;
        [SerializeField] private float angleLerpPerSecond = 18f;

        [Header("Cursor")]
        [SerializeField] private bool lockCursor = true;

        [Header("Ground")]
        [Tooltip("Never let a chase or orbit camera fall below this height above the car, so " +
                 "pitching down cannot put the view under the plane.")]
        [SerializeField]
        private float minHeightAboveTargetM = 0.4f;

        private Camera _camera;
        private Rigidbody _targetBody;
        private int _viewIndex;

        // Live polar state. Yaw and pitch are absolute in world terms for the chase and orbit
        // views, and relative to the car for the first-person ones.
        private float _yawDeg;
        private float _pitchDeg;
        private float _distanceM;
        private float _targetYawDeg;
        private float _targetPitchDeg;
        private float _targetDistanceM;
        private float _mouseIdleForS;
        private Vector3 _followVelocity;

        // Free fly keeps its own position, because it is the one view not derived from the car's
        // transform. Held here rather than read back off transform.position so a view switch away
        // and back does not inherit wherever the chase camera happened to leave the object.
        private Vector3 _flyPosition;
        private Vector3 _flyVelocity;

        /// <summary>The view currently active.</summary>
        public CameraView CurrentView =>
            (views != null && views.Length > 0) ? views[Mathf.Clamp(_viewIndex, 0, views.Length - 1)] : null;

        /// <summary>Name of the active view, for a HUD or a log line.</summary>
        public string CurrentViewName => CurrentView != null ? CurrentView.name : "(none)";

        /// <summary>
        /// Append the free fly view to any scene that was saved before it existed.
        ///
        /// **This is here because a serialised array beats a field initialiser, always.** The
        /// `views` default in this file lists six entries, but every scene in this project was
        /// saved carrying five, and Unity restores what the scene holds rather than what the code
        /// declares. Without this, adding a view to the code would appear to work, compile clean,
        /// and then do nothing in all five scenes, with the digit key silently ignored because the
        /// shortcut loop is bounded by `views.Length`.
        ///
        /// Fixing it here rather than by hand editing five `.unity` files: the YAML edit would have
        /// to be repeated for every scene, would show up as a diff in scenes this feature has no
        /// business touching, and would still not help a scene someone creates tomorrow.
        ///
        /// Idempotent by construction, since it looks for the kind rather than counting.
        /// </summary>
        private void EnsureFreeFlyView()
        {
            if (views == null)
            {
                views = System.Array.Empty<CameraView>();
            }

            foreach (CameraView existing in views)
            {
                if (existing != null && existing.kind == ViewKind.FreeFly)
                {
                    return;
                }
            }

            var grown = new CameraView[views.Length + 1];
            System.Array.Copy(views, grown, views.Length);
            grown[views.Length] = new CameraView
            {
                name = "Free fly",
                kind = ViewKind.FreeFly,
                pivotOffset = new Vector3(0f, 1.0f, 0f),
                distanceM = 10f,
                pitchDeg = 16f,
                fovDeg = 60f,
            };
            views = grown;
        }

        private void Awake()
        {
            EnsureFreeFlyView();

            _camera = GetComponent<Camera>();
            if (target != null)
            {
                _targetBody = target.GetComponent<Rigidbody>();
            }

            SetView(startViewIndex, announce: false);
        }

        private void OnEnable()
        {
            ApplyCursorState(lockCursor);
        }

        private void OnDisable()
        {
            ApplyCursorState(false);
        }

        private void LateUpdate()
        {
            if (target == null || CurrentView == null)
            {
                return;
            }

            ReadViewShortcuts();
            ReadMouse();
            UpdateAngles();
            Place(Time.deltaTime);
        }

        private void ReadViewShortcuts()
        {
            Keyboard keyboard = Keyboard.current;
            if (keyboard == null)
            {
                return;
            }

            if (keyboard.cKey.wasPressedThisFrame)
            {
                SetView(_viewIndex + 1, announce: true);
            }

            // Number keys pick a view outright, which is quicker than cycling when you are
            // checking one specific thing.
            Key[] digits =
            {
                Key.Digit1, Key.Digit2, Key.Digit3, Key.Digit4, Key.Digit5, Key.Digit6,
            };
            for (int i = 0; i < digits.Length && i < views.Length; i++)
            {
                if (keyboard[digits[i]].wasPressedThisFrame)
                {
                    SetView(i, announce: true);
                }
            }

            if (lockCursor && keyboard.escapeKey.wasPressedThisFrame)
            {
                ApplyCursorState(false);
            }
        }

        private void ReadMouse()
        {
            Mouse mouse = Mouse.current;
            if (mouse == null)
            {
                return;
            }

            // Only steer while the cursor is captured, or moving the mouse to another window
            // would spin the view.
            bool captured = !lockCursor || Cursor.lockState == CursorLockMode.Locked;
            Vector2 delta = captured ? mouse.delta.ReadValue() : Vector2.zero;

            if (delta.sqrMagnitude > 0f)
            {
                _targetYawDeg += delta.x * yawDegPerPixel;
                _targetPitchDeg += (invertPitch ? delta.y : -delta.y) * pitchDegPerPixel;
                _mouseIdleForS = 0f;
            }
            else
            {
                _mouseIdleForS += Time.deltaTime;
            }

            ClampAngles();

            float scroll = captured ? mouse.scroll.ReadValue().y : 0f;
            if (!Mathf.Approximately(scroll, 0f) && CurrentView.kind != ViewKind.FirstPerson)
            {
                // Scroll arrives as notches of about 120 on Windows and 1 elsewhere, so only
                // the sign is portable.
                _targetDistanceM = Mathf.Clamp(
                    _targetDistanceM - (Mathf.Sign(scroll) * zoomMetresPerNotch),
                    CurrentView.minDistanceM,
                    CurrentView.maxDistanceM);
            }
        }

        private void ClampAngles()
        {
            CameraView view = CurrentView;
            if (view.kind == ViewKind.FirstPerson)
            {
                // Relative to the car: a driver can look over their shoulder, not spin freely.
                _targetYawDeg = Mathf.Clamp(_targetYawDeg, -firstPersonYawLimitDeg, firstPersonYawLimitDeg);
                _targetPitchDeg = Mathf.Clamp(_targetPitchDeg, -firstPersonPitchLimitDeg, firstPersonPitchLimitDeg);
            }
            else
            {
                _targetPitchDeg = Mathf.Clamp(_targetPitchDeg, minPitchDeg, maxPitchDeg);
            }
        }

        private void UpdateAngles()
        {
            CameraView view = CurrentView;
            bool idle = _mouseIdleForS >= recentreDelayS;

            switch (view.kind)
            {
                case ViewKind.FirstPerson:
                    // Look returns to straight ahead once the mouse settles, so the driver is
                    // never left staring sideways at speed.
                    if (idle)
                    {
                        _targetYawDeg = Mathf.MoveTowards(_targetYawDeg, 0f, recentreDegPerSecond * Time.deltaTime);
                        _targetPitchDeg = Mathf.MoveTowards(_targetPitchDeg, 0f, recentreDegPerSecond * Time.deltaTime);
                    }
                    break;

                case ViewKind.ChaseLocked:
                    // The mouse does not steer this view. Yaw tracks the car with lag, which
                    // is what gives a chase camera its sense of weight.
                    _targetYawDeg = target.eulerAngles.y;
                    _targetPitchDeg = view.pitchDeg;
                    break;

                case ViewKind.FreeOrbit:
                    if (idle && IsMovingForward())
                    {
                        _targetYawDeg = Mathf.MoveTowardsAngle(
                            _targetYawDeg, target.eulerAngles.y, recentreDegPerSecond * Time.deltaTime);
                    }
                    break;

                case ViewKind.FreeFly:
                    // Deliberately nothing. Recentring would swing the camera back behind a car
                    // the operator has just flown away from, which is the one thing this view
                    // exists to avoid.
                    break;
            }

            float rate = view.kind == ViewKind.ChaseLocked ? view.yawFollowPerSecond : angleLerpPerSecond;
            float tYaw = 1f - Mathf.Exp(-rate * Time.deltaTime);
            float tRest = 1f - Mathf.Exp(-angleLerpPerSecond * Time.deltaTime);

            _yawDeg = Mathf.LerpAngle(_yawDeg, _targetYawDeg, tYaw);
            _pitchDeg = Mathf.Lerp(_pitchDeg, _targetPitchDeg, tRest);
            _distanceM = Mathf.Lerp(_distanceM, _targetDistanceM, tRest);
        }

        private bool IsMovingForward()
        {
            if (_targetBody == null)
            {
                return true;
            }

            return Vector3.Dot(_targetBody.linearVelocity, target.forward) > recentreMinSpeedMs;
        }

        private void Place(float deltaTime)
        {
            CameraView view = CurrentView;
            Vector3 anchor = target.TransformPoint(view.pivotOffset);

            if (view.kind == ViewKind.FirstPerson)
            {
                // Rides with the body, then applies the bounded look offset on top.
                transform.position = anchor;
                transform.rotation = target.rotation * Quaternion.Euler(_pitchDeg, _yawDeg, 0f);
                return;
            }

            if (view.kind == ViewKind.FreeFly)
            {
                PlaceFreeFly(deltaTime);
                return;
            }

            // Spherical to Cartesian: the rotation carries the polar angles, and the camera
            // sits one radius back along its own forward axis.
            Quaternion orbit = Quaternion.Euler(_pitchDeg, _yawDeg, 0f);
            Vector3 wanted = anchor - (orbit * Vector3.forward * _distanceM);

            float floor = target.position.y + minHeightAboveTargetM;
            if (wanted.y < floor)
            {
                wanted.y = floor;
            }

            transform.position = view.followSmoothTime > 0f && deltaTime > 0f
                ? Vector3.SmoothDamp(transform.position, wanted, ref _followVelocity, view.followSmoothTime)
                : wanted;

            transform.rotation = Quaternion.LookRotation(anchor - transform.position, Vector3.up);
        }

        /// <summary>
        /// Fly the camera under keyboard control, in the direction it is currently facing.
        ///
        /// **Movement is relative to the camera, not to the world**, so W goes where you are
        /// looking rather than along a fixed axis. That is what makes a free fly usable for
        /// following a corner: aim, then push forward.
        ///
        /// **There is no ground clamp here**, unlike the chase and orbit views. Those clamp
        /// because a chase camera dipping under the plane is always a bug; here going below the
        /// track is a legitimate thing to want, to look at the barrier geometry from underneath.
        /// </summary>
        private void PlaceFreeFly(float deltaTime)
        {
            Vector3 wish = Vector3.zero;
            Keyboard keyboard = Keyboard.current;

            if (keyboard != null)
            {
                if (keyboard.wKey.isPressed) wish += transform.forward;
                if (keyboard.sKey.isPressed) wish -= transform.forward;
                if (keyboard.dKey.isPressed) wish += transform.right;
                if (keyboard.aKey.isPressed) wish -= transform.right;

                // Q and E rather than the pitch of the camera, so height can be changed without
                // also changing where the shot is aimed.
                if (keyboard.eKey.isPressed) wish += Vector3.up;
                if (keyboard.qKey.isPressed) wish -= Vector3.up;

                if (wish.sqrMagnitude > 1e-6f)
                {
                    wish = wish.normalized * flySpeedMs;
                    if (keyboard.leftShiftKey.isPressed || keyboard.rightShiftKey.isPressed)
                    {
                        wish *= flyBoostFactor;
                    }
                }
            }

            // Smoothed rather than applied raw, so releasing a key coasts to a stop instead of
            // cutting. On a wide shot the cut reads as a dropped frame.
            _flyVelocity = flySmoothTime > 0f && deltaTime > 0f
                ? Vector3.Lerp(_flyVelocity, wish, 1f - Mathf.Exp(-deltaTime / flySmoothTime))
                : wish;

            _flyPosition += _flyVelocity * deltaTime;

            transform.position = _flyPosition;
            transform.rotation = Quaternion.Euler(_pitchDeg, _yawDeg, 0f);
        }

        /// <summary>Switch to a view by index. Wraps, so it is safe to call with index + 1.</summary>
        public void SetView(int index, bool announce)
        {
            if (views == null || views.Length == 0)
            {
                return;
            }

            _viewIndex = ((index % views.Length) + views.Length) % views.Length;
            CameraView view = views[_viewIndex];

            // Entering a view adopts its configured placement rather than inheriting whatever
            // the previous one happened to be left at.
            _targetDistanceM = Mathf.Clamp(view.distanceM, view.minDistanceM, view.maxDistanceM);
            _distanceM = _targetDistanceM;

            if (view.kind == ViewKind.FirstPerson)
            {
                _targetYawDeg = 0f;
                _targetPitchDeg = 0f;
            }
            else
            {
                _targetYawDeg = target != null ? target.eulerAngles.y : 0f;
                _targetPitchDeg = view.pitchDeg;
            }

            _yawDeg = _targetYawDeg;
            _pitchDeg = _targetPitchDeg;
            _mouseIdleForS = 0f;
            _followVelocity = Vector3.zero;

            if (view.kind == ViewKind.FreeFly)
            {
                // Enter where a chase camera would have been, so pressing 6 reframes rather than
                // teleports. Computed rather than read off transform.position, which may still be
                // mid-smoothing from the view being left.
                Vector3 anchor = target != null ? target.TransformPoint(view.pivotOffset) : Vector3.zero;
                Quaternion orbit = Quaternion.Euler(_pitchDeg, _yawDeg, 0f);
                _flyPosition = anchor - (orbit * Vector3.forward * _distanceM);
                _flyVelocity = Vector3.zero;
            }

            if (_camera == null)
            {
                _camera = GetComponent<Camera>();
            }

            if (_camera != null)
            {
                _camera.fieldOfView = view.fovDeg;
            }

            if (announce)
            {
                Debug.Log($"[CameraRig] view {_viewIndex + 1}/{views.Length}: {view.name}");
            }
        }

        /// <summary>
        /// Place the camera for the current view straight away, with no smoothing.
        /// Used by editor tooling to preview a view without entering play mode.
        /// </summary>
        public void ApplyImmediate()
        {
            if (target == null || CurrentView == null)
            {
                return;
            }

            Place(0f);
        }

        private static void ApplyCursorState(bool locked)
        {
            Cursor.lockState = locked ? CursorLockMode.Locked : CursorLockMode.None;
            Cursor.visible = !locked;
        }
    }
}
